# TSK-0138 — Protokoll (PR-0012, Auftrag 1 von drei: AC-1 Bündel-Prägung, AC-2 die Wiederholungsläufe)

Rolle: harness-implementer (opus / high). Basis: `07691ba`. Patch: `git diff 07691ba`
(neu und noch untracked: `tools/close_measured_pass.py`, `tools/test_close_measured_pass.py`).
Kein Commit, kein Push, keine Prägung.

---

## 0. Der verworfene Weg (FR-0084)

Verworfen wurde **eine eigene Automaten-Kante `TRIAGED -> FIXED` für den bewiesenen Fall**
(DEC-0086 Option B). Grund: sie nimmt dem Nutzer die Entscheidung ganz aus der Hand — der Bestand
wird dann von einer Ableitung geschlossen und nicht von einer Antwort —, und `DEC-0051 (2)` hat
dafür ausdrücklich eine eigene Runde reserviert. Was der kleinere Weg *nicht* abgedeckt hätte: die
Bindung des Abschlusses an eine **vom Nutzer unterschriebene Liste mitsamt Beweis pro Eintrag**.
Genau die ist hier der Träger — die Option nennt `BUG-nnnn (EVD-nnnn)` je Eintrag, und
`gate_approval` vergleicht diesen Text Zeichen für Zeichen.

---

## 1. AC-1 — die Bündel-Prägung (Kernel)

Neue Freigabe-Art `verification` (`approvals.VERIFICATION_KIND`), Zeilen-Art (kein Item):

- `request-approval verification --batch BUG-a BUG-b …` → **eine** offene Anfrage; das Subjekt ist
  die Liste der Datensätze `{item, revision, scope_hash, evidence}` (`verification_batch`, Resolver
  `cli._verification_bugs` — die Ids werden getippt, der **Beweis wird gelesen**, mit demselben
  Leser, den die bestätigende Kante benutzt: `report.qa_verdicts(..., CONFIRMATION_QUESTION)`).
- `build_question` schreibt **den Satz mit der Anzahl**, die **Option mit der Liste**
  (`TARGET_FORMS` / neu `OPTION_FORMS`). Gemessen am echten Bestand (10er-Bündel):
  Satz 224 Zeichen, Option 764 Zeichen.
- Die Prägung (`mint` → `_close_what_the_batch_lists`) läuft jeden gelisteten Fehler über **seinen
  eigenen Automaten** `OPEN/TRIAGED -> APPROVED -> FIXED -> VERIFIED` und archiviert ihn. Nichts ist
  fest verdrahtet: welche Typen eine Art schließt, sagt `batch_closing_types` (aus
  `APPROVAL_TRANSITIONS`), wie weit gelaufen wird `batch_walk_end` (aus `confirming_edge`), ob
  archiviert wird `is_terminal`. Deshalb bewegt `plan` — die andere listen-gebundene Art — nichts.
- Verweigert **mit Namen zur Anfragezeit** (`batch_walk_blockers`, ein Leser für beide Momente,
  Anfrage und Prägung): kein bestandener `test`-Nachweis, der den Fehler nennt (BUG-0090s Regel);
  ein Fehler jenseits der Kante, die die Freigabe stiftet; ein Typ, für den die Art keine Kante hat.
- `assert_apr_in_force` entscheidet jetzt am **Datensatz** statt an der Art, ob eine Freigabe an
  eine Liste gebunden ist (`listed_items`: Eintrag zählt, wenn er Id **und** unterschriebene
  Inhalts-Prüfsumme trägt). Der Deckungs-Test ist damit **einer** für `plan` und `verification`
  (`_assert_the_list_covers`, Prüfsumme über `listed_content_hash`).

### Prozessmessung auf einem **scaffoldeten** Piloten (`.../TSK-0138/pilot`, `pilot.py`)

| | gemessen |
|---|---|
| A) Anfrage mit einem unbelegten Fehler | `rc=1`, Text nennt `BUG-0003` und die fehlende `test`-Evidenz |
| B) Frage | Satz nennt die Anzahl, Option listet `BUG-0001 (EVD-0001); BUG-0002 (EVD-0002)` |
| B1') Inhalt eines gelisteten Fehlers zwischen Frage und Klick geändert | `rc=0` des Haken, **nichts** geschlossen, **keine** Freigabe, Anfrage bleibt offen |
| C) PreToolUse, Frage wortgleich | `rc=0` |
| D) PreToolUse, Satz umformuliert | `rc=2` — „ist NICHT die Frage, die der Kernel erzeugt hat" |
| E) PreToolUse, **eine Id in der Option** getauscht | `rc=2` (gleiche Verweigerung) |
| F) PostToolUse mit der Freigeben-Option | `rc=0`, `approval APR-0001 recorded for verification` |
| G) beide Fehler | `status: VERIFIED`, `approval_ref: APR-0001`, archiviert |

### Prozessmessung gegen eine **Kopie des echten Bestands** (`realbatch.py`, ausgelieferter Stand)

211 Evidenz-Datensätze, 207 aktive Fehler; erste echte Bündelzeile aus AC-2:

- `request-approval …` `rc=0` in **26,2 s**
- `PreToolUse` wortgleich `rc=0`
- `PostToolUse` `rc=0` in **28,0 s** → **10 von 10** archiviert `VERIFIED`, `approval_ref APR-0038`
- **2,80 s je geschlossenem Fehler.** Option 449 Zeichen (die 764 in der ersten Fassung waren die
  eines 25er-Bündels, nicht dieses).
- **Das Haken-Budget ist NICHT die Grenze**, und die erste Fassung hatte hier eine falsche Zahl
  („47 %"): ein Kit-Haken läuft gegen `_kernel.DEFAULT_WINDOW_SECONDS` (560 s) minus
  `DEADLINE_RESERVE_SECONDS` (1,5 s) — 28,0 s sind davon **5,0 %**.
  **`BATCH_LIMIT = 10` steht aus zwei anderen Gründen:** die Kernel-Sperre hat eine TTL von 60 s
  (`ProjectState(lock_ttl=60.0)`), und ein Lauf, der sie überschreitet, riskiert, dass ein anderer
  Prozess die Sperre als abgestanden bricht — 28,0 s sind knapp die Hälfte davon; und die Liste
  steht im Optionstext, den ein Mensch lesen muss, bevor er klickt.

### Der abgebrochene Lauf (`interrupt.py`) — die Behauptung im Kommentar, gemessen

| Abbruch | Ergebnis |
|---|---|
| nach 8 s | 0 von 10 geschlossen, **keine** Freigabe geschrieben (noch in der Vorprüfung) |
| nach 18 s | 4 von 10 archiviert, `APR-0038` geschrieben |
| danach, ohne zweite Frage | `transition BUG-0021 APPROVED / FIXED / VERIFIED` je `rc=0`, `archive rc=0` |
| Nebenwirkung | der getötete Haken lässt die Kernel-Sperre stehen; sie altert über ihre TTL aus (gemessen: danach `rc=0`) |

Der mitten im Lauf getroffene Eintrag steht auf `FIXED` — er wird mit `transition <id> VERIFIED`
fertiggemacht, nicht mit `APPROVED`.

---

## 2. AC-2 — die Wiederholungsläufe (nach Prüfrunde 1 neu gefahren)

**Was sich gegenüber Runde 1 geändert hat (Blocker B2):** die Auswahl kommt **nicht mehr** aus der
Erhebungszeile. Deren `first:`-Knoten ist der erste Knoten irgendeines Laufs und muss den Fehler gar
nicht messen — BUG-0002 („robocopy /MOVE liest als Kopie") war mit
`test_board.py::test_a_hostile_field_cannot_add_an_element_or_an_attribute_to_the_page` zitiert,
BUG-0074 mit einem Knoten, dessen Docstring von BUG-0071 handelt; 63 der 98 Zeilen zitieren Läufe
mit mehr als einem Knoten. BUG-0090s Regel wird jetzt wörtlich gelesen (DEC-0100 (3)):
**ein Fehler schließt auf den Tests, die ihn NENNEN.** `nodes_naming` parst `tools/test_*.py` und
`.claude/hooks/test_gates.py` mit `ast` und ordnet einen Treffer der Testfunktion zu, deren Spanne
ihn enthält — Dekoratoren eingeschlossen, weil dort die `parametrize`-Fall-Id steht.

`tools/close_measured_pass.py`, ein Knoten nach dem anderen, je mit eigener Frist, Protokoll **LF**
unter `project_memory/staging/TSK-0138/rerun.log`. **Die Tabelle steht dort und nur dort** — hier
die Zusammenfassung:

- 98 `MEASURED-PASS`-Zeilen, alle Items aktiv.
- **49 Fehler werden von mindestens einem Test genannt** (171 Knoten, 1 bis 21 je Fehler).
  **49 bestanden, 0 nicht mehr bestanden** — ein Fehler besteht nur, wenn **jeder** ihn nennende
  Test besteht; der erste rote beendet seinen Lauf. EVD-0227 … EVD-0282, Zusammenfassung jeweils
  „tests naming BUG-nnnn: k nodes, all passed", `--run-command` die pytest-Zeile mit allen k Knoten.
- **49 Fehler nennt kein Test** → zurückgehalten für Auftrag 2: *sie brauchen einen schließenden
  Test, keinen Klick.* BUG-0014, BUG-0034, BUG-0062, BUG-0102, BUG-0106, BUG-0133, BUG-0136,
  BUG-0162, BUG-0167, BUG-0174, BUG-0176, BUG-0178, BUG-0180, BUG-0181, BUG-0190, BUG-0192 … BUG-0197,
  BUG-0201 … BUG-0203, BUG-0207, BUG-0210 … BUG-0214, BUG-0220, BUG-0222 … BUG-0226, BUG-0230,
  BUG-0233 … BUG-0243, BUG-0246 (die vollständige Liste druckt `--plan-only`).
- **4 zurückgehalten** durch PR-0012 AC-3 (Befund 3.1): BUG-0058, BUG-0074, BUG-0075, BUG-0076.
- → **45 schließbar in 5 Fragen** (Runde 1 meldete 94 in 10; die Differenz von **49** ist genau die
  Menge, für die es keinen nennenden Test gibt).

**Die Nachweise aus Runde 1 (EVD-0105 … EVD-0226) bleiben stehen als das, was sie sind:** Läufe des
jeweils ersten Erhebungsknotens, protokolliert in `rerun-first-node.log`. Sie sind **nicht** der
Beweis des Bündels — `report.qa_verdicts` nimmt je Art den **neuesten** Datensatz, und das sind die
neuen.

### Die Bündelzeilen für den Lead

```
python scripts/harness.py request-approval verification --batch BUG-0001 BUG-0002 BUG-0003 BUG-0004 BUG-0005 BUG-0006 BUG-0007 BUG-0009 BUG-0011 BUG-0012
python scripts/harness.py request-approval verification --batch BUG-0013 BUG-0015 BUG-0018 BUG-0020 BUG-0021 BUG-0028 BUG-0029 BUG-0035 BUG-0036 BUG-0038
python scripts/harness.py request-approval verification --batch BUG-0039 BUG-0040 BUG-0041 BUG-0042 BUG-0043 BUG-0044 BUG-0045 BUG-0047 BUG-0048 BUG-0049
python scripts/harness.py request-approval verification --batch BUG-0050 BUG-0051 BUG-0059 BUG-0060 BUG-0061 BUG-0063 BUG-0064 BUG-0065 BUG-0066 BUG-0068
python scripts/harness.py request-approval verification --batch BUG-0070 BUG-0071 BUG-0072 BUG-0073 BUG-0078
```

Im Repo wird die Zeile ohne `scripts/harness.py` gefahren:
`PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory request-approval verification --batch …`.
Die Zeilen sind mit `tools/close_measured_pass.py` (ohne `--evidence`) jederzeit neu druckbar.

---

## 3. Befunde, die dieser Auftrag NICHT schließt, sondern benennt

**3.0 B1 und B2 aus Prüfrunde 1 sind GESCHLOSSEN**, nicht benannt: B1 als fünfte Frage in
`batch_walk_blockers` (die Deckung jedes gelisteten Eintrags, vor dem ersten Schreibvorgang,
alles-oder-nichts) mit dem Geschwistertest dazu; B2 als `nodes_naming` plus die Regel „jeder
nennende Test muss bestehen" und „kein nennender Test → zurückgehalten". Beide rot-zuerst
gemessen (§4, Zeilen B1/B2/B2b/B2c/B2d).

**3.1 Zwei Eingaben des Auftrags widersprechen sich.** Die Erhebung führt BUG-0058, BUG-0074,
BUG-0075 und BUG-0076 als `MEASURED-PASS`; **PR-0012 AC-3 nennt dieselben vier als noch zu
behebende Fehler**. Ein Klick hätte sie geschlossen — genau der „Bestand lügt"-Defekt, den dieses
Ziel beseitigen soll, nur in die andere Richtung. Der Lauf hält sie deshalb zurück, und zwar
**abgeleitet**: `close_measured_pass.held_back_by` liest die Ids aus dem AC-3-Text des Ziel-Items
selbst. Entscheidung: Lead/Nutzer.

**3.2 Die Kosten der Deckungsprüfung wachsen mit dem Evidenz-Bestand — und dieser Auftrag hat ihn
fast verdoppelt.** Gemessen auf einer Kopie des echten Bestands:
`report.qa_verdicts(<ein Item>, CONFIRMATION_QUESTION)` = **2,18 s**, während
`qa_verdicts_by_subject` über **denselben** Bestand **0,21 s** braucht. Der Unterschied ist
`evidence_covers` → `_hangs_from` → `state.read_anywhere` (**3,2 ms je Sprung**), und die
Vorfahren-Menge eines Nachweises wird **pro Ziel neu** berechnet, obwohl sie vom Ziel gar nicht
abhängt. Route: die gedeckte Menge **einmal je Nachweis** bilden und dann nur noch Mitgliedschaft
prüfen. Folge, wenn es offen bleibt: `BATCH_LIMIT` muss mit wachsendem Bestand kleiner werden.
Nicht hier gemacht — es ist eine Änderung an `report.py`/`state.py` mit eigener Messung.

**3.3 Der getötete Haken lässt die Kernel-Sperre stehen** (gemessen, 3.1 oben, Tabelle
„Nebenwirkung"). Die nächste Kernel-Zeile wird mit „kernel lock busy" abgewiesen, bis die TTL
abläuft. Kein Datenverlust, aber eine Verweigerung, die wie ein zweiter Schreiber aussieht.

**3.4 `approval_card` sagt bei einer Bündel-Freigabe „für keinen Vorgang".** Sie liest nur den
APR-Datensatz, und der trägt bewusst nur die Prüfsumme (eine zweite kanonische Kopie der Liste wäre
genau der Defekt, den der Kommentar an `mint` beschreibt). Dieselbe Lücke hat `plan` seit FR-0074.
Bewusst nicht angefasst.

**3.5 Bereichs-Überschreitung, benannt:** `tools/test_staging_cli.py` steht nicht im
`allowed_scope` des Items. Dort war ein Fixture-Eintrag (`SUBJECT_SAMPLES["bugs"]`, 8 Zeilen)
nötig, weil der Test **jede** Zeilen-Art über ihre Bauer-Signatur baut. Die Alternative wäre
gewesen, die Verweigerung „leeres Bündel" im Kernel aufzuweichen — das wäre der schlechtere Tausch.
Abnahme: Lead.

**3.6 Eine Falschaussage im ausgelieferten Text, von der Kernel-Prüfung selbst aufgedeckt.** Nachdem
`(BUG, verification)` neben `(BUG, scope)` stand, schrieb `report._needs` in jede Zeile der
„Bestand lügt"-Auswertung: „needs a `scope` approval **and** a `verification` approval". Die beiden
sind **Alternativen** — eine von beiden läuft die Kante. Für einen Leser hieß das: besorge zwei
Freigaben, wo eine genügt. Repariert: ein „or" innerhalb der Freigabe-Arten, ein „and" davor zur
Evidenz; rot-zuerst als M21.

**3.7 Ein Messfehler in eigener Sache, protokolliert, weil er die Zwischenzahlen erklärt.** Der
erste Durchgang meldete drei Zeilen als „besteht nicht mehr" (BUG-0059, BUG-0178, BUG-0180). Ursache
war **nicht** der Code, sondern der fehlende Versionsstempel: nach einer Kit-Änderung ohne
`bump_kit_version.py` fallen die `test_kitupdate`-Knoten. Nach dem Stempel bestehen alle drei.
Hausregel 7 in Aktion; jede Zeile mit einem `test_kitupdate`-Knoten wurde nach dem **letzten**
Stempel neu gemessen (BUG-0059/0068/0072/0078/0167/0178/0180/0242 → EVD-0219 … EVD-0226).

**3.9 Ein zweiter roter Test, den erst die neue Auswahlregel fand.**
`tools/test_presets.py::test_every_target_form_names_a_live_apr_kind` ist ein zweiseitiger
Stolperdraht: er verlangt, dass eine neue lesbare Form **mit** einer Messung dessen ankommt, was sie
rendert. Er war rot, seit `verification` eine Form hat — und Runde 1 hat ihn nicht gefahren, weil
meine Suiten-Auswahl ihn nicht nannte. Gefunden hat ihn die B2-Regel: `test_presets.py` nennt
BUG-0071, also gehört der Knoten zu dessen Messung. Eingetragen mit dem Zeiger auf die beiden
messenden Tests. **Zweite Bereichs-Überschreitung** (Datei nicht im `allowed_scope`) — Abnahme: Lead.

**3.10 Das Zurückhalten ist jetzt der größere Posten als das Schließen.** 49 von 98 Fehlern nennt
kein Test. Das ist kein Defekt dieses Auftrags, sondern sein ehrliches Ergebnis: die Erhebung hat
„ein Test lief grün" gemessen, nicht „dieser Fehler ist gemessen behoben". Für Auftrag 2 heißt das:
49 Fehler brauchen einen schließenden Test, bevor sie überhaupt in eine Frage dürfen.

**3.8 Ein zweiter Schreiber war während dieses Laufs im Zustand, und zwar nicht ich.** `git status`
zeigt `D project_memory/product/active/PR-0001..0003.yaml` und neue `APR-0032 … APR-0037`, alle
zwischen 14:56 und 14:58 geschrieben, alle `minted_via: user_answer_via_approval_hook`. Das ist die
Drei-Klick-Abnahme der V2-Wurzeln, die PR-0012 `out_of_scope` ausdrücklich als eigene Sache führt;
die drei Items liegen als `ACCEPTED` im Archiv, nichts ist verloren. Nur damit die Löschungen im
Status niemandem als Teil dieses Pakets gelesen werden.

---

## 4. Rot-zuerst (Kopie ohne `.git` unter `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0138/tree`)

Rig: `rig.py` — verweigert den Lauf außerhalb des eigenen Verzeichnisses, öffnet jede Datei
**binär**. Tabelle: `red-first.txt`. Jede Mutation einzeln gesetzt, Knoten gefahren, zurückgesetzt;
Grün-Nachlauf am Ende: `16 passed`.

| Mutation | Test, der rot wird | rc |
|---|---|---|
| M1 `mint` ruft den Bündel-Lauf nicht mehr | `test_the_batch_mint_walks_every_listed_bug_to_verified_and_archives_it` | 1 |
| M8 `state.archive` statt `_archive_locked` | derselbe (Sperre nicht reentrant) | 1 |
| M2 bestätigender Nachweis wird nicht mehr gefragt | `test_a_bug_without_a_passing_test_evidence_is_refused_from_the_batch_by_name` | 1 |
| M3 Kettenposition wird nicht mehr geprüft | `test_a_bug_past_the_edge_the_batch_commits_is_refused_from_it_by_name` | 1 |
| M4 `BATCH_LIMIT` unbegrenzt | `test_a_batch_longer_than_the_limit_is_refused_at_the_builder` | 1 |
| M5 Option wiederholt den Satz | `test_the_batch_option_names_every_listed_bug_and_its_evidence` | 1 |
| M6 `_names_the_item` → alter Id-Vergleich | `test_a_batch_approval_authorises_only_the_bugs_it_lists` | 1 |
| M7 Deckungs-Prüfsumme fällt weg | `test_a_batch_stops_covering_a_bug_whose_content_moved_after_the_question` | 1 |
| M9 `listed_items` ohne Prüfsummen-Bedingung | `test_only_a_manifest_of_signed_item_records_reads_as_a_list` | 1 |
| M10 `--batch`-Besitzer fest verdrahtet | `test_the_batch_flag_belongs_to_the_kinds_whose_resolver_reads_it` | 1 |
| M11 Liste wird zur Prägezeit nicht neu gefragt | `test_a_batch_that_moved_since_the_question_closes_nothing_at_all` | 1 |
| M12 **beide** Index-Neubauten entfernt | `test_a_batch_mint_leaves_the_index_as_fresh_as_a_per_step_rebuild_would` | 1 |
| M13 Rückhalte-Regel ignoriert | `test_a_defect_the_same_goal_assigns_to_another_route_is_held_back_from_every_batch` | 1 |
| M14 Nachweis auch bei `fail` | `test_a_row_whose_test_no_longer_passes_earns_no_evidence_and_is_reported` | 1 |
| M15 Protokoll im Textmodus | `test_the_log_is_written_with_lf_endings_only` | 1 |
| M16 kein Wiederaufsetzen | `test_the_log_is_the_resume_point_so_a_finished_row_is_not_measured_twice` | 1 |
| M17 Bündelschnitt als Literal 25 | `test_the_batch_lines_are_cut_at_the_kernels_own_limit_and_name_every_id_once` | 1 |
| M18 Frist-Zweig entfernt | `test_a_node_that_never_answers_is_a_failure_and_not_a_pass` | 1 |
| M20 Aktiv-Verzeichnis als Literal | `test_the_active_filter_finds_the_store_the_kernel_actually_writes_into` | 1 |
| **B1** Deckung der signierten Liste nicht neu geprüft | `test_a_batch_whose_signed_CONTENT_moved_closes_nothing_and_mints_nothing` | 1 |
| **B2** Knoten nicht die des Fehlers | `test_a_pass_is_recorded_as_a_declared_selection_naming_the_node` | 1 |
| **B2b** der erste Knoten entscheidet | `test_a_defect_passes_only_when_every_test_that_names_it_passes` | 1 |
| **B2c** unbenannter Fehler nicht zurückgehalten | `test_a_defect_no_test_names_is_held_back_for_the_order_that_writes_one` | 1 |
| **B2d** Dekorator-Spanne ignoriert | `test_the_evidence_comes_from_the_tests_that_name_the_bug_and_from_no_other_node` | 1 |
| M21 Route verbindet die Freigabe-Arten mit „and" | `test_the_route_says_or_between_approval_kinds_and_and_before_the_evidence` | 1 |

**Zwei Behauptungen, die zuerst NICHT rot wurden, und was daraus wurde** (beide vom Rig gefunden,
nicht vom Prüfer):

1. M11 lief zunächst auf `rc=0` — die Vorprüfung in `mint` war von keinem Test gedeckt. Der Fall,
   den nur sie abdeckt (halb geschlossenes Bündel, Freigabe geschrieben, Anfrage verbraucht), ist
   jetzt `test_a_batch_that_moved_since_the_question_closes_nothing_at_all`.
2. M19 lief zunächst auf `rc=0` — die Zeile „RED WITHOUT dem `::`" im Docstring war **falsch**, weil
   keiner der negativen Fälle überhaupt `first:` trug. Der Testfall
   `"2/2 passed, first: tools/test_kernel.py"` (Datei statt Knoten) wurde ergänzt; danach rot.

Dazu ein dritter Fund in eigener Sache: `test_no_optional_argument_of_transition_can_skip_the_
approval_check` zählte die optionalen Parameter **beider** Einstiegspunkte auf, probierte sie aber
ausschließlich an `transition`. Ein Umgehungs-Parameter nur an `_transition_locked` — dem
Einstiegspunkt, den jeder prozessinterne Aufrufer benutzt, die Prägung eingeschlossen — war damit
von nichts gedeckt. Jetzt wird jeder Einstiegspunkt mit seinen **eigenen** Parametern geprüft.

---

## 5. Gefahrene Läufe (kein Volllauf — Gate 5)

| Lauf | warum |
|---|---|
| `tools/test_approvals_dispatch.py` (voll) | die geänderte Fläche selbst: 212 passed |
| `tools/test_close_measured_pass.py` (voll) | das neue Werkzeug: 12 passed |
| `tools/test_kernel.py` | liest `state`/`cli`: 131 passed |
| `tools/test_state.py` | liest `transition`/`archive`, beide geändert: 61 passed |
| `tools/test_report.py` | liest `closing_route`/`_needs` über `required_approval_kinds`: 127 passed |
| `tools/test_board.py` | liest jeden Kernel-Schreiber gegen den Index-Neubau: 77 passed |
| `tools/test_staging_cli.py` | baut jede Zeilen-Art über ihre Bauer-Signatur: 98 passed |
| `tools/test_presets.py` | der Stolperdraht über `TARGET_FORMS`: 34 passed |
| `tools/test_light_kit.py -k "approval or question or kind"` | die Freigabe-Frage: 2 passed |
| `tools/test_hooks.py -k "approval or mint or verdict"` | die Haken-Registrierung: 48 passed |
| `tools/test_hooks_v2.py -k approval` | Pre/Post des Freigabe-Haken: 87 passed |
| `tools/test_role_contracts.py` | die drei geänderten SKILL.md: 32 passed |
| `tools/test_repo_hygiene.py` | Zeiger in ausgelieferten Kit-Dateien: 32 passed |
| `tools/test_kitupdate.py` | stempel-empfindlich, nach dem letzten Bump: 86 passed, 1 skipped |
| `kernel.cli --root project_memory validate` | der Zustands-Validator liest die 98 Nachweise (er fand 3.6) |
| `tools/test_e2e.py` | die Kommandofläche: 20 passed |
| `python tools/bump_kit_version.py` | letzter Stempel: dev/office/research `2026.09.11-17` |
| `python -m ruff check tools team-kits` | All checks passed |
| `python tools/validate.py` | all structural checks passed |

Spiegel: `hooks/gate_approval.py` wurde **nicht** geändert; die drei Kopien sind weiterhin
byte-identisch (`a44623dc2c5e20db6a3a14e50ade9080`). Die drei SKILL.md sind kit-eigen und
unterscheiden sich ohnehin.

---

## 6. (g) — Kosten dieses Auftrags

| | |
|---|---|
| Modell / Stufe | Opus 5, effort high |
| Wanduhr | 2026-09-11 14:52:07 → 18:25 (inkl. Nacharbeit nach Prüfrunde 1), **≈ 3 h 33 min** |
| Token (eigener Zähler, Kontext-Restanzeige) | 14 964 588 → 14 491 248, **≈ 473 000** |
| Prozessmessungen | 4 Piloten (scaffoldet, repo-groß, abgebrochen, echte Bündelzeile) |
| Rot-zuerst-Läufe | 26 Mutationen, 25 Zeilen, alle rot (Runde 1: 22/21) |
| Wiederholungsläufe | Runde 1: 98 Erhebungsknoten; Runde 2: 171 nennende Knoten über 49 Fehler, dazu 11 Neumessungen nach Stempeln |

---

## 7. DEC-0100 — erfasst; was die Texte jetzt zitieren

Der Vorschlag aus Runde 1 ist als **DEC-0100** erfasst (DEC-0086 (2) abgelöst, DEC-0086 archiviert).
Jede Stelle, die „DEC-0086's batch form" sagte, nennt jetzt `DEC-0100`: die drei SKILL-Absätze
(dev/office/research) und der Kopfkommentar an `VERIFICATION_KIND` sowie die Zeile an
`APPROVAL_TRANSITIONS`. `decisions/` selbst habe ich nicht angefasst.
