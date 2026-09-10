# TSK-0131 — Strom G5-1 „Bestandsbereinigung" (PR-0008, AC-1..AC-7)

Umsetzer-Protokoll. Arbeitsbaum: `C:/Offline Repos/v2-testbed/_worktrees/g5-stock` (Branch
`g5/stock`, Stand b7f282e). Scratch: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0131/`.
Zustandsschreibungen (AC-1/AC-2/AC-6) laufen durch den Kernel im Hauptcheckout
`C:/Offline Repos/AgentAndSkills` (`PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory …`).
Tier: **Opus 5, effort high** (DEC-0081, Nutzerentscheidung 2026-09-05; ersetzt DEC-0077 (4)/DEC-0080 (8)).

**Uhr, gelesen (`date`), nie hochgerechnet:** Vorgänger-Agent (Fable) 21:21–22:07; dieser Umsetzer
Beginn 22:10:46, Zwischenstände 22:23:00 / 22:53:27 / 23:04:34 / 23:09:19 / 23:47:42, Abschluss siehe
Abschnitt 12.

---

## 0. Vorgefunden (gemessen, vor jeder eigenen Änderung)

Ein Vorgänger-Agent auf Fable lief 21:21–22:07 und wurde von der Stufenentscheidung DEC-0081
gestoppt. Was er hinterlassen hat, wurde gemessen und **behalten**, nicht neu gebaut:

| Was | Zustand | Urteil dieses Umsetzers |
|---|---|---|
| `redfirst`-fähiges Scratch mit `probes.py`, `probes2.py`, `make_copy.py`, `kernel_writes.py` | Rigs halten die Regel (verweigern außerhalb ihres Verzeichnisses, schreiben mit ausdrücklicher Zeilenenden-Politik) | **behalten**, weiterverwendet |
| `survey-runs.tsv` (307 Läufe), `survey-tests-by-source.tsv`, `holes-presence.tsv`, `probes.log`, `ci-b7f282e-failed.log` | echte Messungen gegen b7f282e | **behalten**, Grundlage von AC-1/AC-6 |
| AC-3 im Arbeitsbaum: `report.confirmed_but_open` + `stock_rollup` + `cli validate`-Zweig + 2 Tests | grün; **ein Defekt gefunden** (Abschnitt 5) | behalten, korrigiert |
| AC-4 im Arbeitsbaum: `NONEMPTY_FIELDS["TSK"]`, `_check_nonempty_fields`, Remedy-Default, 2 Tests + 12 Fixture-Anpassungen | grün | behalten |
| BUG-0087-Zusatz: `test_no_assertion_in_the_suites_is_statically_true` + Entfernung der `or True`-Zeile | grün | behalten |
| `dec-decision-catcher.json`, `dec-bug-closing-route.json` | zwei DEC-first-Vorlagen an den Nutzer | **behalten**, unverändert weitergereicht |
| Archivierungen im Hauptstore (BUG-0083..0086, BUG-0089, TSK-0121..0129) | 21:32 durch den Kernel gelaufen | AC-6-Teil erledigt vorgefunden |

**Zwei Über-Verweigerungen des Repo-Gates, die auch diese Runde getroffen haben** (dokumentiert,
keine Löcher): `robocopy <repo> <scratch>` und jede schreibfähige Zeile mit einem `$`- oder
`{`-Wort sind rc 2 (H19 bzw. der Platzierungs-Leser). Alle Rigs dieser Runde stehen deshalb als
`.py`-Dateien im Scratch und werden mit absoluten Pfaden gestartet.

---

## 1. Plan — und der verworfene Weg in einer Zeile (FR-0084-Form)

**AC-7, mechanische Hälfte:** gebaut wird ein **Kernel-Kommando** `sweep-pointers`
(`report.pointer_sweep`), das die Dateien des Projekts über `git ls-files` holt und jede
Backtick-Zitation prüft, die auf nichts zeigt. **Verworfen:** die mechanische Hälfte als **Haken**
oder als Zweig von `validate` zu bauen — ein Haken hätte auf der Merge/Push-Zeile von
`gate_memory_complete` gelegen, wo ein zusätzlicher Baumlauf in die Frist läuft (ein getöteter Haken
ist ein Durchlass), und ein `validate`-Zweig hätte den Fall „kein git" still als „keine Befunde"
gedruckt. **Was der kleinere Weg nicht abgedeckt hätte:** die Rollen-Texte und die Prosa des
Projekts — `validate` liest Items, nicht Dateien.

**AC-5:** die Regel als **eine Frage** in §7 der dev-Verfassung („Ist das freigegebene ZIEL noch
das, was wir bauen wollen?"), plus ein Test, der die Route **aus dem ausgelieferten Text liest**,
gegen den Kernel-Vertrag hält und sie auf einem echten Pilot **läuft**. **Verworfen:** den CR-Typ
zu entfernen (die zweite Option von AC-5) — er ist vollständig gebaut (Automat, Felder,
Freigabebindung, V1-Migration); entfernt hätte man den Vertrag, nicht den Defekt. **Korrigiert in
Nacharbeit 1 (R6):** hier stand, office und research trügen dieselbe Frage bereits — gemessen
tragen sie die Frage **CR gegen BUG** und nicht **CR gegen Wurzelersatz**, und `SUPERSEDED` kommt in
keiner der beiden Verfassungen vor. Research hat die Regel jetzt (sein `RQ` trägt denselben
Automaten wie `PR`), office bekommt sie nicht (`PROC` endet in `RETIRED`). **Nicht abgedeckt:** ob ein PM die Frage
im Betrieb wirklich stellt — das liest kein Gate.

**AC-1:** Verdikte nur, wo eine Messung sie trägt; die Lücke zwischen „Test besteht" und „Fehler
behoben" wird **benannt statt geraten** (Abschnitt 4 und `H179`).

---

## 2. DEC-first-Vorschläge (an den Lead; der Nutzer entscheidet)

| Datei | Frage | Stand |
|---|---|---|
| `dec-decision-catcher.json` | FR-0012: woran sagt eine Entscheidung, dass sie Bauarbeit verlangt? (A Feld `work` + Zeigerrichtung / C nur Zeigerrichtung / keins) | **wartet** — der Fänger ist deshalb **nicht gebaut**, wie der Auftrag es vorsieht |
| `dec-bug-closing-route.json` | AC-1/AC-6: Weg eines reparierten Bugs zu VERIFIED (A Münzung je Bug / B Automatenkante / C Evidenz und warten) | **wartet** — der Strom hat Option A vorbereitet (Evidenz liegt, Zeilen stehen in Abschnitt 6) |

---

## 3. Nahttabelle (empfangen / erwartet beim Merge)

| Datei | Geteilt mit | Was ich geschrieben habe | Was der Merge tun muss |
|---|---|---|---|
| `team-kits/kernel/cli.py` | G5-2, G5-3 (eigene Kommandoblöcke) | ein Unterparser `sweep-pointers` (nach `validate`) + sein Zweig in `main()` + der Stock-Rollup im `validate`-Zweig | Blöcke aneinanderhängen; die Kommandoliste in **beiden** Verfassungen-Sätzen und im README muss **jedes** neue Kommando nennen (`tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it` — hat diese Runde rot gemeldet) |
| `team-kits/kernel/report.py` | keiner in G5 | `confirmed_but_open`, `stock_rollup`, `_check_nonempty_fields`, `pointer_sweep` + Leser | anhängen |
| `team-kits/kernel/state.py`, `backlog_types.py` | keiner | `NONEMPTY_FIELDS["TSK"]`, Remedy-Default | anhängen |
| `team-kits/kernel/holes.py` | keiner | `_prose_link`, `_index_row_count` erweitert, Kopfzeile des Index | anhängen |
| `team-kits/*/constitution/AGENTS.md` | G5-2 (Leiter-Sätze/Pins), G5-3 (Korrespondenzrolle) | **§5a: die Kommentardisziplin, byte-identisch ×3** (1859 B je Datei, ein Hash); **§0-Kommandoliste: `sweep-pointers` ×3**; **dev §7: die CR-Frage** (nur dev) | Absätze zusammenführen; die Byte-Identität der Kommentar-Pflicht ist Bedingung (`tools/test_role_contracts.py::test_a_paragraph_the_constitutions_share_is_one_text`) |
| `team-kits/*/agents/*.md` | G5-2 (model/effort-Pins) | ein Satz Kommentarpflicht in **9** bauenden Rollendefinitionen, byte-identisch | zusammenführen |
| `.claude/agents/harness-*.md` | meine | DEC-0080 Regeln 1/2/3/7 (lead), 6 (verifier), Modell/Effort-Absatz + Gate-5-Korrektur (implementer) | — |
| `tools/lead_package_sizes.json` + `docs/reviews/phase0-disposition.md` | alle | **3 Einträge journalisiert** (nicht überschrieben): +837 B (Kommentarpflicht), +1383 B (CR-Frage, nur dev), +18 B (Kommandoliste) | Journal ist additiv; nach dem Merge einmal `python tools/record_lead_package_sizes.py --write --note "…"` |
| `README.md` | alle | `sweep-pointers` in der Kommandoliste + ein Absatz, was es liest und was **nicht** | zusammenführen |
| `tools/**` | alle | neue Datei `tools/test_pointer_sweep.py`; Änderungen in test_report, test_state, test_migrate_holes, test_repo_hygiene, test_review_procedure, test_hooks, test_hooks_v2, test_kernel, test_staging_cli | — |
| `team-kits/*/VERSION` | alle | Stempel — der gültige Stand steht **einmal**, in N20 | **VERSION-Hunks sind NICHT im Patch**; der Merge stempelt einmal neu |

---

## 4. Abnahmezeilen je Kriterium

### AC-1 (FR-0058-Bestandsaufnahme) — TEILWEISE, der Rest ist benannt

* **Tabelle:** `project_memory/staging/TSK-0131/survey-table.md`, **196 Zeilen** = jedes aktive
  BUG-Item, mit Stand, Lochnummer, Verdikt, Evidenz und der gemessenen Zeile.
* **Gemessen** (307 Testläufe gegen b7f282e, 21:33–22:05, plus 12 Sondierungen in `probes.log`):
  106 `MEASURED-PASS`, 6 `MEASURED-OPEN`, 52 `OPEN-BY-DESIGN` (migrierte Löcher im Stand TRIAGED,
  deren Item selbst der Nachweis der offenen Lücke ist), 32 `UNMEASURED`.
* **Was NICHT geliefert ist, und warum es kein Verdikt gibt:** ein bestandener Test, der einen Bug
  NENNT, sagt nicht, dass der Bug weg ist — bei einem migrierten Loch ist es meist genau der Test,
  der die Lücke **festnagelt** (`BUG-0111`/H19: der Test behauptet die Über-Verweigerung, um die es
  geht; er besteht, weil die Lücke da ist). Aus dem Laufausgang 106 Verdikte abzuleiten hätte 106
  falsche Zustände durch den Kernel geschrieben. Die Lücke ist als **`BUG-0261` (H179)** erfasst,
  mit der Messung und mit dem, was stattdessen begrenzt.

### AC-2 (die Wünsche) — GELIEFERT, mit einer benannten Grenze

| FR | Verdikt | Gemessene Zeile |
|---|---|---|
| FR-0048 | **MERGED**, `resulting_item: TSK-0076`, archiviert | `user/claude/CLAUDE.md` Zeile 3 trägt die Regel und nennt FR-0048 als gemessenen Anlass |
| FR-0064 | **MERGED**, `resulting_item: TSK-0105`, archiviert | `grep -c "^memory:"` = 0 bei dev quality-engineer, research reviewer, office bookkeeper; 9 andere Rollen tragen den Schlüssel weiter |
| FR-0069 | **MERGED**, `resulting_item: TSK-0105`, archiviert | die Design-Brief-Pflicht steht in §5a Schritt 5 der dev-Verfassung; dev ist das einzige Kit mit einer `product-designer`-Rolle (über alle drei `agents/`-Verzeichnisse gemessen) |
| FR-0072 | **MERGED**, `resulting_item: TSK-0111`, archiviert | `team-kits/*/skills/humanizer/` existiert in allen drei Kits, und ein echter Scaffold installiert sie (`[ok] skill: humanizer`); offen ist nur das Geschmacksurteil, das DEC-0080 dem Nutzer stellt |
| FR-0058 | TRIAGED, `related_pr` von PR-0003 auf **PR-0008** gezogen | dieser Wunsch **ist** das Ziel PR-0008 |
| FR-0043 | TRIAGED, nachgemessen | `grep -in "bench\|p95\|latency" .github/workflows/*.yml` = kein Treffer; nicht gebaut |
| FR-0019/0020/0022/0023/0024/0025 | TRIAGED, `source` trägt die Zurückstellung | „DEFERRED BLOCK, Nutzerurteil 2026-09-04/05, DEC-0080 (9): need more planning" |
| FR-0002, FR-0004, FR-0007, FR-0012, FR-0015, FR-0033, FR-0047, FR-0073, FR-0081, FR-0088 | **unverändert** | sie hängen an laufenden Strömen (G5-2: FR-0047/FR-0088 unter PR-0010; G5-3: FR-0033/FR-0073 unter PR-0009) oder an dieser Runde selbst (FR-0007/FR-0012 zeigen bereits auf PR-0008). Ein Zustandsschreiben von mir hätte sich mit einem parallel laufenden Strom überschrieben — das ist die **benannte Grenze** dieses Kriteriums |

### AC-3 (das ableitbare „Erledigt") — GELIEFERT und am echten Store gemessen

`report.confirmed_but_open` fragt dieselbe Evidenz-Ableitung eine zweite Frage: besteht die
**bestätigende** Evidenz des Items (`state.CONFIRMING_EVIDENCE`), während sein Stand noch offen
liest? Gedruckt neben den Befunden von `validate`, nicht unter ihnen — die Route braucht eine
Münzung, die das Projekt selbst nicht laufen kann.

**Gemessen am Store dieses Repos (23:00, `validate` in der Merge-Sicht):**

```
Stock lies upward: 5 item(s) whose confirming Evidence passes while their status still reads open
  BUG-0025 OPEN (test EVD-0086): OPEN -> TRIAGED -> APPROVED (needs a 'scope' approval) -> FIXED -> VERIFIED …
  BUG-0033 OPEN (test EVD-0087) … BUG-0088 (EVD-0088) … BUG-0090 (EVD-0089) … BUG-0091 (EVD-0090)
```

### AC-4 (BUG-0023) — GELIEFERT

`NONEMPTY_FIELDS` gewinnt `("TSK", "expected_outputs")` — **eine** Karte, die die Erfassungstür
(`state.capture_preflight`) und der Validator (`report._check_nonempty_fields`) lesen, also beide
Eingänge (`create-task` und `capture TSK` enden in `state.capture`). Der Validator nennt gespeicherte
Aufträge als **Warnung**, weil `TSK_PLAN_FIELDS` das Feld außerhalb von DRAFT einfriert und ein
Fehler eine Reparatur verlangen würde, die kein Kommando fahren kann.

### AC-5 (BUG-0022) — GELIEFERT, auf einem echten Pilot gelaufen

* **Text:** dev-Verfassung §7 gewinnt die **eine Frage**, die zwischen CR und Wurzelersatz
  entscheidet, mit dem gemessenen Anlass (`BUG-0022`, Pilot 4) und dem Stand, den die ersetzte
  Wurzel bekommt (`SUPERSEDED`).
* **Verhalten:** `tools/test_hooks.py::test_a_change_to_something_built_walks_the_CR_route_the_constitution_names`
  liest die Route **aus dem ausgelieferten Text**, vergleicht sie mit `AUTOMATA["CR"]` und
  `APPROVAL_TRANSITIONS[("CR","scope")]` und **läuft sie** auf einem Projekt, das die echten
  Installer erzeugt haben: `capture CR` → `CR-0001 DRAFT` in `changes/active/`, Freigabefrage vom
  Kernel gestellt und durch den **projekteigenen Haken** gemünzt → `APPROVED`, `transition APPLIED`
  → `APPLIED`; danach `transition PR-0001 SUPERSEDED` → der Ersatzweg bleibt und wird verzeichnet.
  1 passed in 10.83 s.

### AC-6 (Generation-4-Reste) — GELIEFERT bis zur Nutzer-Münzung

| Item | Verdikt | Evidenz / gemessene Zeile |
|---|---|---|
| BUG-0025 | Bestätigende Evidenz liegt | **EVD-0086**, 6 passed in 8.46 s, in einem echten git-Arbeitsbaum (die Scratch-Kopie überspringt diese Tests mit „not a git work tree") |
| BUG-0033 | Bestätigende Evidenz liegt | **EVD-0087**, 2 passed in 64.87 s; die Last-Hälfte bleibt offen und trägt ihr eigenes Item (H162/BUG-0244) |
| BUG-0088 | Bestätigende Evidenz liegt | **EVD-0088**, 2 passed in 15.27 s; AC-2 des Bugs (lädt eine schlüssellose Rolle einen vorhandenen Baum?) bleibt unbeantwortet |
| BUG-0090 | Bestätigende Evidenz liegt | **EVD-0089**, 3 passed in 2.90 s |
| BUG-0091 | Bestätigende Evidenz liegt | **EVD-0090**, 2 passed in 27.53 s |
| BUG-0069 | **bleibt OPEN**, nachgemessen | **EVD-0091** (`result: fail`): `gh run 33985882966` (b7f282e, 43m36s) ist weiter `failure` — aber **1** Fehler auf windows-latest und **2** auf ubuntu-latest statt 6/34 plus ~250 ERRORS. **Beide** identifiziert und **in dieser Runde repariert**; die eine Zeile, die noch wartet, ist der gehostete Lauf nach dem Merge-Push |
| BUG-0083..0086, BUG-0089 | archiviert | vorgefunden, 21:32 durch den Kernel |
| TSK-0121..0126 (+0127..0129) | archiviert | vorgefunden, 21:32 durch den Kernel |
| PR-0004..PR-0007 | **wartet auf den Nutzer** | `transition PR-0004 IN_DELIVERY` ist rc 1: „the transition a delivery approval commits, and none is in force" — der Weg ist eine **Lieferfreigabe je Ziel** |

### AC-7 (FR-0007 + FR-0012) — erste Hälfte GELIEFERT, zweite wartet auf den Nutzer

* **Verfassungen:** die Kommentardisziplin steht als **ein** Absatz in §5a („die Pflichten, hinter
  denen kein Gate steht"), **byte-identisch in allen drei** (1859 B, ein SHA-256). Der alte Absatz
  („A comment says what the code cannot", §14) ist **entfernt** — zwei Fassungen derselben Regel
  sind genau der Defekt, den SR-0008 meint. Alle vier Klauseln stehen drin: Zeiger auf ein Item;
  eine Eigenschaftsbehauptung wird ein Test, den der Satz NENNT; kein Satz behauptet eine Prüfung,
  die der Code nicht baut; eine Zahl lebt an genau einem Ort.
* **Rollendefinitionen:** ein Satz, byte-identisch, in **9** bauenden Rollendefinitionen
  (dev: backend-developer, devops-engineer, frontend-developer, quality-engineer; office:
  office-developer; research: data-analyst, research-engineer, researcher, reviewer). **Welche
  Rollen bauen, ist abgeleitet und nicht getippt:** eine Rolle, deren SKILL die FR-0007-Regel
  nennt, ist die Rolle, die in diesem Kit Code schreibt.
* **Mechanische Hälfte:** `python scripts/harness.py sweep-pointers`. Auf diesem Repo gemessen:
  **26 tote Zeiger** gegen den b7f282e-Store (vor den Verengungen des Lesers: 118). Im Arbeitsbaum
  meldet er heute **31**, und die fünf zusätzlichen sind dieselbe Store-Naht wie in Abschnitt 10:
  `DEC-0080` steht in `tools/test_review_procedure.py` (5 Nennungen) und liegt im **Hauptstore**,
  nicht im b7f282e-Store des Arbeitsbaums. In der Merge-Sicht verweigert der Sweep ehrlich
  („git could not list this project's files … so this sweep has no subject") — die Kopie ist kein
  git-Baum, und genau dafür gibt es `PointerSweepUnavailable`. Auf **je einem Piloten pro Kit** gelaufen
  (`tools/test_pointer_sweep.py::test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy`,
  3 passed in 18.09 s — echter `init_project_memory` + echter `scaffold_team` + das installierte
  `scripts/harness.py sweep-pointers`).
* **FR-0012:** **nicht gebaut**, wartet auf die Nutzerentscheidung (`dec-decision-catcher.json`).
  Der Auftrag sieht genau das vor; der Fänger ist in einer Runde nachgebaut, sobald die Antwort da
  ist.

---

## 5. Der Defekt, den die vorherige Korrektur eingeführt hat

`report.stock_rollup` (vom Vorgänger) baute seine Zeile als
`dict(found, item=…, status=item.get("status"), …)`. Das ist genau die Form, die
`tools/test_approvals_dispatch.py::test_no_direct_status_write_can_produce_a_status_an_approval_commits`
als Statusschreiben liest und mit „writes a status this reader cannot bound" verweigert — dieselbe
Form, mit der der alte `mint` einen freigabegebundenen Status geschrieben hat. Gemessen: 1 failed.
Auch die naheliegende Reparatur (`row["status"] = …`) bleibt rot, weil der Leser die
Index-Zuweisung ebenso liest. Gebaut ist jetzt die Form des Geschwisters
`delivery_closure_rollup`: ein **Dict-Display**, Feld für Feld. Danach: 123 passed.

---

## 6. Was auf den NUTZER wartet (Zeilen stehen fertig)

> **Stand dieses Abschnitts: überholt.** Die Frage ist beantwortet (`DEC-0086`, N12), fünf der sechs
> Münzungen sind vom Lead gefahren, `BUG-0069` wartet auf den gehosteten Lauf. Was heute noch offen
> ist, steht **einmal**, in **N20**.

**Sechs Scope-Münzungen** (Weg: TRIAGED → APPROVED, dann `transition FIXED`, `transition VERIFIED`,
`archive` — alles Kernel-Zeilen, die die Sitzung selbst fahren kann), sobald
`dec-bug-closing-route.json` beantwortet ist:

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory request-approval scope BUG-0025
… dasselbe für BUG-0033, BUG-0088, BUG-0090, BUG-0091   (BUG-0069 bleibt OPEN)
```

**Vier Lieferfreigaben** für die Generation-4-Ziele:

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory request-approval delivery PR-0004
… dasselbe für PR-0005, PR-0006, PR-0007
```

**Eine Entscheidung** je DEC-Vorlage (Abschnitt 2).

---

## 7. Leser-Mutationen (DEC-0080 (6)) — je neuem Leser eine, in der Richtung, die sein Docstring bestreitet

Rig: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0131/redfirst.py` — kopiert den Arbeitsbaum in
den Scratch, mutiert **eine** Sache, fährt **eine** Auswahl; verweigert den Lauf außerhalb seines
eigenen Verzeichnisses; öffnet jede Datei mit ausdrücklicher Zeilenenden-Politik; eine Mutation,
deren `old` nicht in der Datei steht, ist ein **RIG-ERROR** und kein stilles Überspringen.

| Leser | Mutation (Richtung, die der Docstring bestreitet) | Auswahl | Ergebnis |
|---|---|---|---|
| `holes._prose_link` | immer verlinken | `test_a_hole_with_no_prose_file_is_a_row_without_a_link` | **RED** 1 failed |
| `holes._prose_link` | nie verlinken | dieselbe | **RED** 1 failed |
| `holes._index_row_count` | nur verlinkte Zeilen zählen | `test_an_empty_store_does_not_empty_a_full_index` | **RED** 1 failed |
| `report._undecorated_citation` | auch links jedes Nicht-Wort-Zeichen abstreifen | `test_the_decoration_around_a_citation_is_not_part_of_it` | **RED** 1 failed |
| `report._CITATION_GLUE_RX` | auch ein einfaches Leerzeichen verkleben | dieselbe + Klassen-Test | **RED** 2 failed |
| `report._TEST_NODE_RX` | einen blanken Dateinamen als Knoten akzeptieren | `test_a_dead_test_pointer_and_a_dead_item_pointer_are_both_reported` | **RED** 1 failed |
| `report._lies_in_a_kit_tree` | `return False` | `test_a_kit_tree_inside_the_project_is_not_the_projects_own_code` | **RED** 1 failed |
| `report._swept_files` (git-Verweigerung) | `if listed.returncode != 0:` → `if False:` | `test_a_project_git_cannot_list_refuses_instead_of_sweeping_clean` | **RED** 1 failed |
| `report.SCAFFOLDED_ROOT_FILES` | Tupel leeren (Stolperdraht-Ende „nicht tot") | Pilot-Test ×3 Kits | **RED** 3 failed |
| Verfassungs-Absatz (Kommentarpflicht) | in einem Kit umformulieren | `test_every_constitution_carries_the_comment_discipline_duty` | **RED** |
| dito | die mechanische Hälfte herausnehmen | dieselbe | **RED** |
| dito | Absatz aus einer Verfassung entfernen | dieselbe | **RED** |
| Rollendefinition | Satz aus einer Definition entfernen | `test_every_implementing_role_definition_carries_the_comment_duty` | **RED** |
| dito | Satz in einer Definition umformulieren | dieselbe | **RED** |
| `_implementing_roles` (Ableitung) | `FR-0007` aus dem einen office-SKILL nehmen → leere Menge | dieselbe | **RED** |
| `harness-lead.md` | DEC-0080-Regel 3 auf DEC-0070 umbiegen | `test_the_harness_role_texts_carry_the_generation_4_rules_with_their_pointers` | **RED** |
| `harness-verifier.md` | Regel 6 zum Slogan machen (Mechanismus raus) | dieselbe | **RED** |
| CR-Absatz | eine Statusfolge nennen, die der Kernel nicht hat | `test_a_change_to_something_built_walks_the_CR_route_the_constitution_names` | **RED** |
| dito | die Freigabeart weglassen | dieselbe | **RED** |
| dito | den gemessenen Anlass (`BUG-0022`) weglassen | dieselbe | **RED** |
| dito | den Stand der ersetzten Wurzel weglassen | dieselbe | **RED** |
| `approvals.APPROVAL_TRANSITIONS` | die CR/scope-Bindung entfernen | dieselbe | **RED** |
| Loch-Dreieck | Prosadatei löschen / Zeile entfernen / anderes Item nennen / Link umbiegen | `test_every_hole_is_one_index_row_one_prose_file_and_one_item` | **RED** ×4 |

**Alle 27 Mutationen rot.** Eine Mutation lief zuerst **GRÜN** und ist protokolliert, weil sie
etwas über den Leser sagt: `no-subject-reads-as-no-findings` in der ersten Fassung traf den
`OSError`-Zweig, während `git ls-files` in einem Nicht-Repository mit rc 128 zurückkommt — der
Zweig, der wirklich läuft, ist der Rückgabecode-Zweig, und erst dessen Mutation ist rot.

---

## 8. Rote Tests je Fix (ohne den Fix rot, gemessen — nicht behauptet)

| Fix | Test, der ohne ihn rot wird |
|---|---|
| BUG-0023 (leere `expected_outputs`) | `tools/test_state.py::test_a_work_order_that_expects_nothing_is_refused_at_both_entrances`, `tools/test_report.py::test_validate_names_a_stored_order_that_expects_nothing` |
| AC-3 (Stock-Rollup) | `tools/test_report.py::test_a_passing_regression_run_names_the_open_item_as_stock_lying_upward`, `::test_the_stock_line_says_when_the_recorded_test_no_longer_exists` |
| Loch-Index verlinkt ins Leere | `tools/test_migrate_holes.py::test_a_hole_with_no_prose_file_is_a_row_without_a_link` |
| Der veraltete Loch-Tabellen-Test | `tools/test_repo_hygiene.py::test_every_hole_is_one_index_row_one_prose_file_and_one_item` (der alte war auf **jedem** Lauf ab b7f282e rot) |
| BUG-0087 (`assert … or True`) | `tools/test_repo_hygiene.py::test_no_assertion_in_the_suites_is_statically_true` |
| AC-7 mechanische Hälfte | `tools/test_pointer_sweep.py` (5 Tests) |
| AC-7 Texte | `tools/test_review_procedure.py::test_every_constitution_carries_the_comment_discipline_duty`, `::test_the_comment_duty_says_which_half_is_mechanical_and_which_is_not`, `::test_every_implementing_role_definition_carries_the_comment_duty` |
| DEC-0080-Regeln in den Rollentexten | `tools/test_review_procedure.py::test_the_harness_role_texts_carry_the_generation_4_rules_with_their_pointers` + der Boden `::test_the_statement_reader_sees_a_paragraph_and_a_bullet_and_nothing_else` |
| AC-5 (CR) | `tools/test_hooks.py::test_a_change_to_something_built_walks_the_CR_route_the_constitution_names` |
| BUG-0069 (ubuntu) | `tools/test_hooks.py::test_gate_test_scope_says_so_when_it_cannot_place_a_target_at_all` — der gehostete POSIX-Lauf war die Messung, die Reparatur ist ein ausdrücklicher Skip mit Grund (AC-1 des Bugs) |

---

## 9. Was bewusst NICHT geschlossen, aber benannt ist

| Als Item | Was |
|---|---|
| **`BUG-0256` (H174)** | Es gibt keinen zweiten Umsetzer-Steckbrief: Modell und Effort kommen aus der Frontmatter der Rollendefinition, DEC-0081 hält fest, dass der Spawn keinen Effort-Parameter hat — also braucht die Merge-Stufe aus DEC-0081 (2) eine **zweite Datei**, und `allowed_scope` dieses Auftrags nennt genau drei `.claude/agents/*.md` und kein Verzeichnis. Der Lead muss den Bereich weiten. |
| **`BUG-0257` (H175)** | Der Zeiger-Sweep kann eine **Illustration** nicht von einem Zeiger unterscheiden und den Bestand eines fremden Stores nicht vom eigenen: 26 Befunde auf diesem Repo, davon 17 dieser beiden Arten und 9 wirklich tot (`DEC-0001` ×7 — die Id, die BUG-0020 aus diesem Store gelöscht hat — und `tools/conftest.py::V1_MONOLITHS` ×2). |
| **`BUG-0261` (H179)** | Ein bestandener Test, der einen Fehler nennt, ist eine **Messung**, kein Urteil (Abschnitt 4). |
| **`BUG-0262` (H180)** | Ein zweiter Zeitmess-Test (`tools/test_hooks_v2.py::test_the_id_scan_is_linear_on_the_worst_legal_input`) faellt auf einem beschaeftigten Host rot statt zu ueberspringen — dieselbe Klasse wie BUG-0033 AC-2, anderer Test; vorbestehend an b7f282e, allein gruen in 7.54 s. |
| **`BUG-0268` (H185)** | **`CLAUDE.md` sagt „Die vier Gates dieses Repos"**, `.claude/settings.json` registriert seit `FR-0086` **fünf** (`gate_test_scope.py`). `CLAUDE.md` steht in `forbidden_scope` — der Satz gehört korrigiert, aber nicht von mir. (In Runde 1 stand das hier „ohne Item"; seit Nacharbeit 2 ist es als Loch erfasst, N15.) |
| ohne Item, hier benannt | **AC-2 ist an zehn FRs nicht angefasst**, weil sie an parallel laufenden Strömen hängen (G5-2, G5-3). Ein Schreiben von mir hätte deren Zustand überschrieben. |
| ohne Item, hier benannt | **FR-0012** war in Runde 1 nicht gebaut und wartete auf die Nutzerentscheidung. **Überholt:** der Nutzer hat entschieden (`DEC-0083`), gebaut ist es in Nacharbeit 1 (**N2**) — Träger-Zeile im Validator, `work`-Pflicht an beiden Türen. |

---

## 10. Suiten, die gelaufen sind — und WARUM diese (DEC-0080 (2))

Geänderte Regeln und ihre Leser, per `grep` über die Aufrufer ermittelt:

* `report.validate_state` (neuer Befund `_check_nonempty_fields`, neuer Rollup) →
  `grep -ln validate_state`: `tools/test_backlog_types.py`, `test_hooks.py`, `test_hooks_v2.py`,
  `test_kernel.py`, `test_migrate.py`, `test_parallel_scopes.py`, `test_report.py`,
  `.claude/hooks/test_gates.py`.
* `NONEMPTY_FIELDS` / `state.capture_preflight` (Erfassungstür beider Eingänge) →
  `test_report.py`, `test_state.py`, dazu jede Suite, die einen `TSK` erfasst
  (`test_kernel.py`, `test_staging_cli.py`, `test_migrate_holes.py`, `test_hooks.py`).
* `holes.render_index` / `_index_row_count` → `test_migrate_holes.py`, `test_repo_hygiene.py`,
  `test_state.py`, `test_approvals_dispatch.py`, `test_hooks_v2.py`, `.claude/hooks/test_gates.py`.
* Verfassungen / Rollendefinitionen → `test_review_procedure.py`, `test_role_contracts.py`,
  `test_context_budget.py`, `test_parallel_streams.py`, `test_reference_skills.py`, `test_hooks.py`.

**Gefahrene Läufe (jeweils mit Zeitgrenze, immer nur EIN pytest gleichzeitig, keine Last-Rigs):**

| Auswahl | Ergebnis |
|---|---|
| `test_backlog_types, test_kernel, test_migrate, test_parallel_scopes, test_report, test_state, test_staging_cli, test_migrate_holes, test_pointer_sweep` | **639 passed in 406.44s** |
| `test_repo_hygiene, test_approvals_dispatch, test_review_procedure, test_role_contracts, test_context_budget, test_parallel_streams, test_reference_skills` | 370 passed, 3 failed → nach den Korrekturen grün (siehe unten) |
| `test_approvals_dispatch::…status_write…` + `test_report` | **123 passed in 33.36s** (nach der Korrektur aus Abschnitt 5) |
| `test_hooks` (erster Lauf) | 1004 passed, 13 skipped, **1 failed** → Kommandoliste, korrigiert |
| `test_hooks, test_hooks_v2` (Abschlusslauf) | 3142 passed, 13 skipped, **1 failed** — Host-Rot, allein gruen (Abschnitt 12) |
| `.claude/hooks/test_gates.py -k "hole or index or agent or marker or statement or spawn or item"` | 137 passed, 1 failed — die Naht des Dokuments (Abschnitt 12); die VOLLE Gate-Suite ist eine erklaerte Flaeche und wird von Gate 5 verweigert (gemessen: rc 2 mit der Remedy-Zeile) |

**Die drei roten aus dem zweiten Lauf, aufgelöst:** einer war der echte Defekt aus Abschnitt 5;
**zwei** sind kein Defekt, sondern die Store-Naht — `DEC-0080`, `DEC-0081`, `TSK-0131` und
`BUG-0256` liegen im **Hauptstore**, der Arbeitsbaum trägt `project_memory/` im Stand b7f282e.
Gemessen in der Merge-Sicht (`merge_view.py` = dieser Code über dem Store des Hauptcheckouts):
**94 passed, 1 skipped**.

**Die volle Suite ist NICHT gelaufen** und gehört dem Merge: Gate 5 verweigert eine Zeile, die die
ganze erklärte Fläche fährt, ohne den `DELIVERY_RUN`-Präfix — gemessen als echter Haken-Prozess
gegen die b7f282e-Kopie: `python -m pytest tools/ -q` rc **2**,
`DELIVERY_RUN=TSK-0131 python -B -m pytest tools/ -q` rc 0, jede Auswahl rc 0.

---

## 11. Stempel

`python tools/bump_kit_version.py` viermal gefahren (nach jeder Kit-Änderung), zuletzt:
**dev-team 2026.09.05-11, office-team 2026.09.05-10, research-team 2026.09.05-10**. Der Patch
`stream-stock.patch` enthält **keine** VERSION-Hunks. `python -m ruff check .`: All checks passed.
`python tools/validate.py`: all structural checks passed.

## 12. Abschlusslauf, Uhr und Token

**Letzte Laeufe (Uhr gelesen):**

| Wann | Auswahl | Ergebnis |
|---|---|---|
| 23:47-00:20 | `tools/test_hooks.py tools/test_hooks_v2.py` | **3142 passed, 13 skipped, 1 failed in 1916.92s** |
| 00:21 | derselbe eine Test allein | **1 passed in 7.54s** |
| 00:22-00:29 | Merge-Sicht: `test_review_procedure, test_role_contracts, test_context_budget, test_repo_hygiene, test_approvals_dispatch, test_parallel_streams, test_reference_skills` | 360 passed, 10 skipped, 3 failed |
| 00:31 | Merge-Sicht mit den `docs/` des Hauptcheckouts: `test_every_hole_is_one_index_row_one_prose_file_and_one_item` | **1 passed** |
| 00:27 | `.claude/hooks/test_gates.py -k "hole or index or agent or marker or statement or spawn or item"` (Arbeitsbaum) | 137 passed, 1 failed |
| 00:32 | dieselben Loch-Tests in der Merge-Sicht | 11 passed, 1 failed (fremd) |
| 00:33 | `ruff check .` / `tools/validate.py` | All checks passed / all structural checks passed |
| 00:36 | `kernel.cli validate` auf dem Hauptstore | **0 error(s), 67 warning(s)** |

**Die vier roten, jede aufgeloest:**

1. `tools/test_hooks_v2.py::test_the_id_scan_is_linear_on_the_worst_legal_input` — **Host-Rot**,
   nicht Code-Rot: im 32-Minuten-Lauf 0.205 s Kosten gegen 0.052 s Streuung, allein danach
   1 passed in 7.54 s. Vorbestehend an b7f282e, Docstring und Code stimmen ueberein; als
   **`BUG-0262` (H180)** erfasst, weil es die Klasse aus BUG-0033 AC-2 in einem zweiten Test ist.
2. `test_repo_hygiene::test_no_file_a_parser_reads_from_byte_zero_starts_with_a_bom` und
   `::test_every_shipped_role_and_skill_definition_is_a_file_that_check_looks_at` — **Artefakte der
   Merge-Sicht**: `fatal: not a git repository`. Im Arbeitsbaum (echter git-Baum) beide gruen.
3. `test_repo_hygiene::test_every_hole_is_one_index_row_one_prose_file_and_one_item` in der
   Merge-Sicht — die **Naht**: der Arbeitsbaum traegt `docs/POST_V2_WISHLIST.md` im Stand b7f282e,
   der Hauptstore 170 Loecher. Mit den `docs/` des Hauptcheckouts: gruen.
4. `.claude/hooks/test_gates.py::test_every_test_a_hole_names_is_one_that_exists` in der
   Merge-Sicht — **fremd**: H169/H171 (BUG-0251/BUG-0253, erfasst von G5-2) nennen Tests aus
   `tools/test_ladder.py`, die in **meinem** Baum nicht liegen. Loest sich beim Merge auf.

**Ein Seiteneffekt im Hauptcheckout, ausdruecklich genannt:** der Zeigerindex in
`docs/POST_V2_WISHLIST.md` ist mit dem NEUEN Renderer neu geschrieben worden
(`reindex_holes.py` → `index rewritten from the store: 170 hole(s)`), weil sonst 15 Zeilen auf
Prosadateien zeigen, die niemand geschrieben hat. Danach: 155 Links = 155 Prosadateien, 15
unverlinkte Zeilen. Der Merge faehrt `migrate-holes --reindex` nach dem letzten Loch noch einmal.

**Uhr (alles `date`-gelesen, nichts hochgerechnet):** Vorgaenger (Fable) 2026-09-05 21:21-22:07;
dieser Umsetzer 22:10:46 bis 2026-09-06 00:36 — **rund 2 h 25 min** Wandzeit, davon etwa 1 h 20 min
Suitenlaeufe. **Token:** dieser Prozess kann seinen eigenen Verbrauch nicht lesen; die Zahl fuer die
(g)-Tabelle steht im Spawn-Protokoll des Leads und wird hier bewusst NICHT geschaetzt.

**Provisorischer Stempel:** dev-team `2026.09.05-11`, office-team `2026.09.05-10`,
research-team `2026.09.05-10`. **Patch:** `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0131/stream-stock.patch`
— 33 Dateien, **keine** VERSION-Hunks, **kein** `project_memory/`.

**Der Patch ist gegen einen sauberen b7f282e-Baum geprueft** (`patch_check.py` + `patch_check2.py`:
`git archive b7f282e` in ein Wegwerf-Repository, dann `git apply --check`) — **rc 0, „the patch
applies cleanly"**.

> **Zurueckgenommen in der Abschlussrunde (2026-09-06 18:30, gemessen):** hier stand als
> „Nebenbefund", `.gitattributes` fuehre `.claude/` als `export-ignore`, ein `git archive` liefere
> die Rollendefinitionen also nicht mit. Das ist **falsch** und war nie gemessen: `.gitattributes`
> enthaelt die Zeichenkette `export-ignore` an keiner Stelle, und der Wegwerf-Baum aus
> `git archive b7f282e` traegt `.claude/agents/harness-{lead,implementer,verifier}.md` — beides
> nachgesehen. Genau die Art Satz, die diese Runde an anderer Stelle als Befund bekommen hat: eine
> Behauptung ueber eine fremde Datei, die niemand prueft.

**Die Spiegelung** (`hooks/`, `settings/`, `templates/`) ist unberuehrt; dass sie byte-identisch
bleibt, misst der Kit-Audit in `tools/test_hooks.py`, und der Lauf oben ist gruen.

**Kein Commit, kein Push, keine Installation in den globalen Speicher.**


---

# Nacharbeit 1 (nach Pruefrunde 1, FAIL) — 2026-09-06

Uhr gelesen: Beginn 07:23 (DEC-0083 gelesen), Zwischenstaende 07:51:44 / 07:55:54 / 08:58:44.
Gefahren gegen denselben Arbeitsbaum; alle Zustandsschreibungen wieder durch den Kernel im
Hauptcheckout.

## N1. Die vier blockierenden Befunde

### B1 — der Sweep fegte die Kit-Baeume, deren Ausschluss sein Docstring behauptet

**Gebaut:** `kernel.report.installed_kit_paths` — „Kit-Material" wird aus **drei Lesern abgeleitet,
die das Projekt selbst haelt**, statt aus einem Verzeichnisnamen plus drei Dateinamen:

1. die **Durchsetzungsschicht, wie das AUSGELIEFERTE Gate sie definiert**
   (`gate_write_scope._ENFORCEMENT_PATHS`, importiert ueber `scopes._hooks_dir()` — derselbe Import,
   den `scopes.matcher()` macht, aus demselben Grund);
2. die **Provider-Schicht, wie das Projekt sie protokolliert** (`.claude/provider_artifacts.json`,
   `dirs` + `files`);
3. die **Wurzeldateien und Skriptverzeichnisse des Installers** (`SCAFFOLDED_ROOT_FILES`,
   `INSTALLER_SCRIPT_DIRS`) — die beiden unvermeidbaren Aufzaehlungen, mit dem Stolperdraht an
   **beiden** Enden, und der erste Eintrag von `INSTALLER_SCRIPT_DIRS` ist zugesichert **derselbe**
   wie das Verzeichnis von `cli.ENTRY_POINT`, kann also nicht verrotten.

Die Skriptverzeichnisse werden **nur ausgeschlossen, wo ein Kit installiert ist** (Bedingung: der
Einstiegspunkt liegt da) — sonst haette der Kit-Quellbaum sein eigenes `tools/` verloren; gemessen:
unbedingter Ausschluss kostete dieses Repo 7 eigene Befunde.

**Abnahmezeile, je Kit auf einem echten Scaffold gemessen (`pilot_sweep.py`):**

```
dev-team       clean   rc=0  0 dead pointer(s)  {}          planted rc=1  2  {'src': 2}
office-team    clean   rc=0  0 dead pointer(s)  {}          planted rc=1  2  {'src': 2}
research-team  clean   rc=0  0 dead pointer(s)  {}          planted rc=1  2  {'src': 2}
```

vorher (derselbe Rig, alter Code): 39 / 27 / 30 Befunde ohne eine Zeile eigenen Codes.

### B2 — der Pilot-Test konnte an dem nicht scheitern, was er zu messen behauptete

`tools/test_pointer_sweep.py::test_the_root_files_the_sweep_skips_are_installed_and_would_be_noisy`
liest jetzt **Rueckgabecode und Zahl** (`_dead_pointers` liest die gedruckte Zahl; fehlt sie, ist die
Antwort `None` und nicht 0) und misst **beide Enden**: sauberer Scaffold rc 0 / 0, ein eingepflanzter
toter Zeiger in `src/pricing.py` rc 1 / genau 2, mit Datei und beiden Schreibweisen im Text.
Mutation `sweep-reports-nothing-at-all` (`findings_in_text` → `return []`): **RED, 4 failed**.

### B3 — AC-4 schloss genau eine Schreibweise von „erwartet nichts"

**Gebaut:** ein Praedikat, `backlog_types.names_something`, das die **Elemente** liest statt den
Behaelter (`field_elements` als Leser, also zaehlt ein Skalar als das eine Ding, das er ist), und es
wird an **beiden** Enden gefragt — `state.capture_preflight` und `report._check_nonempty_fields`.
Gemessen ueber jede Schreibweise, die der Pruefer gefunden hat: `[]`, `[""]`, `[None]`, `["   "]`,
`[[]]`, `""`, `"   "`, `None`, `["", None, "  "]` werden an **beiden** Eingaengen verweigert und vom
Validator benannt; `["", "src/z.py"]` und der Skalar `"src/y.py"` bleiben legal. Die CLI-Zeile
`--expected-output ""` ist jetzt rc 1.

### B4 — eine ungemessene Eigenschaftsbehauptung im Rollentext

Der Absatz in `.claude/agents/harness-implementer.md` sagt jetzt genau, was gemessen ist und **von
wem**: der Spawn traegt **keinen Effort-Parameter** (`BUG-0251`, gemessen), das **Modell** kann der
Lead am Spawn uebergeben und hat es fuer diesen Lauf getan — *dessen* Messung, nicht meine, denn ein
Subagent hat kein Spawn-Werkzeug, aus dem er eine Parameterliste lesen koennte. Folge: `DEC-0081` (2)
braucht **keine** zweite Datei fuer die Stufe, die es nennt. `BUG-0256` ist damit eine Dublette von
`BUG-0251`, wurde mit der Korrektur im `observed` versehen, auf **DUPLICATE** transitioniert und
archiviert (Kernel-Zeilen, keine Muenzung noetig).

## N2. FR-0012 gebaut (DEC-0083)

| Teil | Wo | Messung |
|---|---|---|
| Feld | `OPTIONAL_FIELDS["DEC"] = (DEC_WORK_FIELD,)`, plus `DEC_WORK_NONE` und `CAPTURE_ONLY_REQUIRED` | gespeicherte Entscheidungen bleiben gueltig (Test: eine ohne Feld ist **kein** Fehler) |
| Tuer | **`kernel/cli.py`, Zweig `capture`** — nicht `state.capture_preflight` | siehe unten |
| Validator | `report._check_decision_carriers`: (a) `work`-Id, die kein Item traegt → **error**; (b) geltende Entscheidung ohne `work`, die **kein** Item nennt → **warning**; (c) `work: none` schweigt | am echten Store gemessen: **10** Entscheidungen ohne Traeger (nachgezaehlt in Pruefrunde 2; die Nacharbeit schrieb 11), danach 0 nach den `work`-Schreibungen |
| Skills | die Klausel steht in **allen drei** Lead-SKILLs, in dem Satz, den die drei Kits byte-identisch teilen | `test_every_lead_skill_says_who_carries_a_decision` |
| Bestand | `work` auf **DEC-0071..0079, DEC-0081, DEC-0082, DEC-0083** durch `update` geschrieben | `kernel-writes.log` |

**Warum die Tuer auf der Kommandoflaeche sitzt und nicht in der Bibliothek — gemessen, nicht
gewaehlt:** in `capture_preflight` band die Pflicht auch den **V1-Import** und die **Quittung** des
Migrationslaufs (`migrate.RECEIPT_TYPE == "DEC"`). Der Import kann sie nicht beantworten, und ihn
auszunehmen braucht einen **Leser** von `IMPORT_MARK` — den `DEC-0021` ausdruecklich verboten hat
(„ein zweiter Riegel neben `approval_ref` sind zwei Antworten auf eine Frage"). Gemessen: mit der
Klausel in der Bibliothek waren **49 Migrationstests rot** und
`test_the_import_mark_says_where_an_item_came_from_and_claims_no_lever` meldete den neuen Leser. Also
bindet die Pflicht die Zeile, die eine Rolle tippt — und ihre Grenze steht im Code: wer
`state.capture` direkt ruft, wird nicht gefragt, weshalb die gespeicherte Haelfte von der
**Zeigerrichtung** beantwortet wird und nicht von dieser Zeile. Die Quittung des Migrationslaufs
traegt jetzt `work: none`, weil sie nichts entscheidet, was jemand bauen muesste — der eine Fall, in
dem der Kernel das Feld selbst schreiben darf, weil die Entscheidung seine eigene ist.

## N3. Zustandsschreibungen dieser Nacharbeit (alle durch den Kernel)

* **AC-1:** `update` mit der **nachgemessenen Kette** auf `BUG-0010`, `BUG-0017`, `BUG-0037`,
  `BUG-0052`, `BUG-0053`, `BUG-0079`, `BUG-0082` — jede Zeile nennt Befehl und Ergebnis (zwei davon
  reproduzieren woertlich: vier von fuenf Compose-Schreibweisen rc 0, die glob-erweiterte
  Haken-Zeile rc 0). `BUG-0069` trug seine Kette schon aus Runde 1.
* **AC-1, CANCELLED/superseded:** `BUG-0256` → **DUPLICATE** (BUG-0251), archiviert.
* **AC-2:** `related_pr` **jetzt** geschrieben, Status **spaeter**: FR-0002/0015/0033/0073/0081 →
  `PR-0009`, FR-0047 → `PR-0010`; jedes `source` sagt, dass der Status auf den fremden Strom wartet.
  FR-0004 nachgemessen und begruendet stehengelassen (die eine Haelfte ist gebaut —
  `docs/reviews/phase0-disposition.md` —, die andere nicht).
* **DEC-0083 (5):** `work` auf zwoelf Entscheidungen.
* **Neue Items:** `BUG-0265` (H183, die Skriptverzeichnis-Ueberverweigerung), `BUG-0267`
  (CLAUDE.md nennt vier Gates, registriert sind fuenf — R9, und die Datei ist fuer jede Rolle
  verbotener Bereich). `BUG-0257` (H175) und `BUG-0262` (H180) nachgeschaerft.

## N4. Die uebrigen Reste des Pruefberichts

| Rest | Erledigt als |
|---|---|
| **R1** die Stock-Zeile unterschied „kein `run_command`" nicht von „alles loest auf" | drei Zustaende statt zwei in `cli.py`; Test erweitert (ein Datensatz ohne Lauf steht mit „names no run, so nothing here can be repeated"). Mutation RED. Nebenbefund beim Bauen: der Leser des Tests fand ZWEI Zeilen zu einer Id — die Lieferungs-Rollup druckt dieselbe Form; er liest jetzt nur den Abschnitt hinter „Stock lies upward:". |
| **R2** H175 nannte die gemessene Rauschklasse nicht | `BUG-0257.observed` nachgezogen: die Kit-Material-Klasse ist **benannt und geschlossen** (39/27/30 → 0/0/0), was bleibt ist Illustration-vs-Zeiger; der Skriptverzeichnis-Rest hat sein eigenes Item. |
| **R3** der Pilot-Test hatte eine **Kopie** der Sweep-Schleife | `report.findings_in_text` ist jetzt der eine Leser, den beide rufen. |
| **R4** die Verfassungen versprachen mehr, als der Sweep baut | derselbe Halbsatz wie im README, byte-identisch ×3; Mutation RED. |
| **R5** drei Tabellenzeilen trugen ein Verdikt, das ihre eigene Zeile nicht stuetzt | die Regel der Tabelle liest jetzt zuerst die **Evidenz** (ein `fail` schlaegt den Laufausgang) und verlangt fuer MEASURED-PASS, dass **jeder** genannte Test bestanden hat; neu: `MEASURED-PARTIAL`. BUG-0069 steht jetzt MEASURED-OPEN mit `EVD-0091/fail` in der Spalte. |
| **R6** zwei Dokumente behaupteten etwas ueber office/research, was dort nicht steht | gemessen: `RQ` traegt denselben Automaten wie `PR` (`SUPERSEDED`), `PROC` endet in `RETIRED`. Also: die **research**-Verfassung bekommt die Wurzelersatz-Regel, office bekommt **keine** — und ein Test haelt beide Richtungen (`test_every_kit_whose_root_can_be_replaced_says_when_to_replace_it`), abgeleitet aus `ROOT_TYPE_BY_KIT` + `AUTOMATA`. Die falsche Behauptung steht unten in Abschnitt 1 korrigiert. |
| **R7** vier Leser ohne Mutation im Protokoll | fuenf Mutationen nachgefahren, alle RED (Abschnitt N5). |
| **R8** der Reindex des Zeigerindex liegt ausserhalb des Patches | steht jetzt in der Nahttabelle als **Merge-Schritt** mit der Zeile. |
| **R9** CLAUDE.md nennt vier Gates | als `BUG-0267` erfasst — die Datei ist fuer jede Rolle verbotener Bereich, also gehoert die Korrektur dem Nutzer. |

## N5. Mutationen dieser Nacharbeit (je neuem Leser eine, Richtung: was der Docstring bestreitet)

| Leser / Text | Mutation | Ergebnis |
|---|---|---|
| `names_something` | fragt wieder den Behaelter (`bool(value)`) | **RED** 2 failed |
| `names_something` | ignoriert Leerzeichen (kein `strip()`) | **RED** 2 failed |
| `names_something` | verweigert einen Skalar | **RED** 2 failed |
| `capture_preflight` | alte Behaelterfrage zurueck | **RED** 1 failed |
| `_check_nonempty_fields` | alte Behaelterfrage zurueck | **RED** 1 failed |
| `installed_kit_paths` | wieder nur Verzeichnisname + Wurzeldateien | **RED** 3 failed |
| `installed_kit_paths` | ohne das ausgelieferte Gate | ~~RED~~ **GRÜN** — siehe N9 |
| `installed_kit_paths` | ohne das Provider-Manifest | ~~RED~~ **GRÜN** — siehe N9 |
| `INSTALLER_SCRIPT_DIRS` | Tupel geleert | **RED** 3 failed |
| `INSTALLER_SCRIPT_DIRS` | Reihenfolge gedreht (Bindung an `ENTRY_POINT` weg) | **RED** 3 failed |
| `findings_in_text` | meldet nichts | **RED** 4 failed |
| `_check_decision_carriers` | nicht registriert | **RED** |
| `_check_decision_carriers` | liest eine Entscheidung als Traeger | **RED** |
| `_check_decision_carriers` | `none` schweigt nicht mehr | **RED** |
| `_check_decision_carriers` | fragt auch abgeloeste Entscheidungen | **RED** |
| `_decisions_items_name` | vergisst den archivierten Traeger | **RED** |
| `CAPTURE_ONLY_REQUIRED` | geleert | **RED** |
| die Tuer in `cli.capture` | Klausel entfernt | **RED** |
| Stock-Zeile | verschweigt den fehlenden Lauf | **RED** |
| `confirmed_but_open` | stellt die Lieferungsfrage | **RED** |
| `confirmed_but_open` | nennt auch Endzustaende | **RED** |
| `_test_nodes_the_tree_no_longer_defines` | immer leer | **RED** |
| `_check_nonempty_fields` | nicht registriert | **RED** |
| Lead-SKILL | verliert die `work`-Klausel | **RED** |
| Lead-SKILL | behaelt die alte Leiter | **RED** |
| Lead-SKILL | loescht die Leiter ohne Ersatz | **RED** |
| research-Verfassung | verliert die Wurzelersatz-Regel | **RED** |
| office-Verfassung | behauptet einen Ersatz, den `PROC` nicht kann | **RED** |
| Kommentar-Absatz | ueberzieht wieder („liest alles") | **RED** 1 failed |

**Zwei dieser Zeilen sind in Pruefrunde 2 als Rig-Artefakt widerlegt worden** und stehen oben korrigiert (Abschnitt N9); alle uebrigen Mutationen dieser Nacharbeit sind **rot**; eine (`carrier-ignores-the-none-silence`) lief in der
ersten Fassung gruen und ist protokolliert: sie traf die aeussere von **zwei** Stellen, an denen
`none` schweigt, und erst die innere ist die, die wirklich entscheidet.

## N6. Naht an G5-2 (Leiter) — und was der Merge tun muss

Die beiden Lead-SKILLs schreiben die Leiter nicht mehr vor. **Korrigiert in Nacharbeit 2
(N-B1):** die erste Fassung behauptete, der Kernel leite die Sprosse ab und schreibe sie auf
Lease, Kopf und Aufgabenitem -- eine Mechanik, die dieses Paket **nicht baut** (`rung` kommt in
keinem Kernelmodul vor), und sie widersprach dem Verfassungsabsatz, auf den sie zeigte. Jetzt
steht dort **keine Kopie der Regel**: die Sprosse und der Effort kommen aus der Leiter dieses
Kits, **so wie der Leiter-Absatz der Verfassung sie festlegt** -- wahr in diesem Baum (dort
steht die nutzergesteuerte Leiter) und wahr nach dem Merge (dort die abgeleitete).

**Merge-Schritt, blockierend:** G5-2s `STALE_LADDER_TEXTS` (in `tools/test_model_ladder.py`) fuehrt
diese beiden Dateien als „traegt noch den alten Text" und misst diese Karte an **beiden** Enden. Nach
dem Merge sind die zwei Eintraege **tot** und muessen aus der Karte entfernt werden:
`team-kits/dev-team/skills/project-manager/SKILL.md` und
`team-kits/research-team/skills/project-manager/SKILL.md`. Die drei
`templates/project_memory/project_config.yaml` bleiben drin — sie sind `templates/**` und damit fuer
diesen Strom **verbotener Bereich**; die exakte Ersetzung dort ist die des Konfigurationsschluessels
`effort_map`/Leiterzeile auf die Werte, die `ladder.yaml` erklaert, und gehoert dem Merge oder einem
eigenen Auftrag.

**Zweiter Merge-Schritt (R8):** nach dem letzten Loch der Generation einmal
`PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory migrate-holes --reindex`, sonst
zeigen die Zeilen der spaeter erfassten Loecher auf Prosadateien, die niemand geschrieben hat. In
dieser Runde zweimal gefahren (170 und 174 Loecher).

## N7. Suiten dieser Nacharbeit

| Auswahl | Ergebnis |
|---|---|
| `test_backlog_types, test_kernel, test_migrate, test_parallel_scopes, test_report, test_state, test_staging_cli, test_migrate_holes, test_pointer_sweep, test_schemas, test_board` | **747 passed in 519.85s** |
| `test_repo_hygiene, test_approvals_dispatch, test_review_procedure, test_role_contracts, test_context_budget, test_parallel_streams, test_reference_skills` | 371 passed, 4 failed → nach der Korrektur der geteilten SKILL-Sektion gruen; die drei uebrigen sind die Store-Naht (`DEC-0083` liegt im Hauptstore) |
| Merge-Sicht: `test_review_procedure, test_repo_hygiene` | 45 passed, 9 skipped, 3 failed → 2 sind die fehlende `.git`-Datei der Kopie, 1 war der Zeigerindex vor dem Reindex; danach gruen |
| `test_hooks, test_hooks_v2` | **3142 passed, 13 skipped, 2 failed in 40:41** — beide Rot waren MEIN Text: die erste Fassung des Leiter-Schritts nannte `ladder.yaml` und `python scripts/harness.py ladder`, die G5-2 baut und mein Baum nicht hat. `test_instruction_files_name_only_state_files_a_v2_project_has` und `test_every_command_a_role_is_handed_is_on_the_entry_points_surface` haben genau das gemeldet. Der Schritt zeigt jetzt auf den **Leiter-Absatz der Verfassung** statt auf Datei und Kommando — wahr in beiden Bäumen —, und die positive Hälfte meines eigenen Tests fragt danach. Nachlauf: siehe unten. |

| Nachlauf `test_hooks, test_review_procedure, test_role_contracts, test_reference_skills` | **1077 passed, 13 skipped, 2 failed in 23:21** — beide Rot sind die **Store-Naht** (`DEC-0080`, `DEC-0083`, `TSK-0131`, `BUG-0251` liegen im Hauptstore, der Arbeitsbaum trägt `project_memory/` im Stand b7f282e). In der Merge-Sicht: **4 passed**, dieselben Tests plus die beiden Zeiger-Tests von `test_repo_hygiene`. |

Die volle Suite bleibt dem Merge (Gate 5, gemessen rc 2 ohne `DELIVERY_RUN`).

## N7a. Die Bestandstabelle nach der Korrektur

Neu erzeugt am Ende der Nacharbeit, 202 Zeilen:
`MEASURED-PASS 102 . OPEN-BY-DESIGN 52 . UNMEASURED 38 . MEASURED-OPEN 8 . MEASURED-PARTIAL 2`.
Der Sweep dieses Repos meldet **31** tote Zeiger — 24 davon nach den Verengungen der Nacharbeit
plus 7, die auf Items dieser Runde zeigen, die im **Hauptstore** liegen und nicht im b7f282e-Store
des Arbeitsbaums (dieselbe Naht wie die zwei roten Tests oben). In der Merge-Sicht verweigert der
Sweep ehrlich, weil die Kopie kein git-Baum ist.

## N8. Stempel, Patch und Uhr der Nacharbeit

`python tools/bump_kit_version.py` nach jeder Kit-Änderung; Stand jetzt **dev/office/research
2026.09.06-7**. `python -m ruff check .`: All checks passed. `python tools/validate.py`: all
structural checks passed. `kernel.cli validate` auf dem Hauptstore: **0 error(s), 67 warning(s)** —
gemessen mit dem Kernel **des Hauptcheckouts**, also dem, den dieses Paket ersetzt (dieselbe
Verwechslung wie in N15, R3-1). Die Zahl des laufenden Kernels steht **einmal**, in N20 (e).

Das Lead-Paket-Journal hat drei weitere Einträge (+837/+1383/+18 aus Runde 1, dann +319/+319/+1287
und ein unveränderter Lauf) — additiv, nichts überschrieben; die falsche Behauptung des ersten
Eintrags über office/research steht **korrigiert daneben**, nicht gelöscht.

**Patch:** `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0131/stream-stock.patch` — 37 Dateien,
**keine** VERSION-, **keine** `project_memory/`-Hunks, `git apply --check` gegen einen sauberen
b7f282e-Baum **rc 0**.

**Uhr (gelesen):** Nacharbeit 07:23–10:21, rund **3 h**, davon etwa 2 h 20 min Suitenläufe
(747 / 371 / 3142+13 / 1077+13). Zusammen mit Runde 1: rund **5 h 25 min** Wandzeit dieses
Umsetzers. **Token:** dieser Prozess kann seinen eigenen Verbrauch nicht lesen; die (g)-Zeile füllt
der Lead aus dem Spawn-Protokoll.


---

# Nacharbeit 2 (nach Pruefrunde 2, FAIL) — 2026-09-06

## N9. Ein Rig-Fehler, den die Pruefrunde aufgedeckt hat — und was er an Abschnitt N5 aendert

Der Pruefer konnte zwei meiner N5-Zeilen nicht nachfahren und bat um die Messflaeche. **Er hatte
recht, und der Fehler lag in meinem Rig:** `redfirst.py` mutierte eine Kit-Datei und fuhr die Auswahl
**ohne neu zu stempeln**. Ein Kit, das nicht mehr auf sein eigenes `VERSION` hasht, laesst jeden
Scaffold mit „does not hash to the `content:` in its own VERSION" abbrechen — der Test wird rot, aber
aus einem Grund, der mit der Mutation nichts zu tun hat. Genau die Fehlschluss-Klasse, die derselbe
Pruefer in Runde 1 (B2) benannt hat.

Das Rig stempelt jetzt nach jeder Mutation unter `team-kits/` neu (`bump_kit_version.py` in der
Kopie). **Nachgemessen, alle scaffoldenden Faelle:**

```
kit-material-drops-the-shipped-gate            GREEN  3 passed      <- war faelschlich RED
kit-material-drops-the-provider-manifest       GREEN  3 passed      <- war faelschlich RED
kit-material-is-a-directory-name-again         RED    3 failed
installer-script-dirs-emptied                  RED    3 failed
installer-script-dirs-lose-the-entry-point-tie RED    3 failed
scaffolded-root-files-tuple-emptied            RED    3 failed
sweep-reports-nothing-at-all                   RED    4 failed
AC-5, alle fuenf (scheitern vor dem Scaffold)  RED    1 failed je
```

**Was das ueber den Code sagt** (und was jetzt auch im Docstring von `installed_kit_paths` steht):
das ausgelieferte Gate und das Provider-Manifest **ueberdecken sich** — jeder allein haelt einen
sauberen Piloten bei 0 Befunden, erst beide zusammen entfernt bringen die 41 zurueck. Keiner der
beiden ist heute einzeln notwendig, und **kein Test kann einen von beiden rot zeigen**. Das ist
Tiefenstaffelung, kein Defekt: was jeder kauft, ist ein Projekt, in dem der andere fehlt. Die dritte
Gruppe (die zwei Aufzaehlungen) ist einzeln tragend, und ihr Stolperdraht zeigt es.

## N10. Die beiden blockierenden Befunde der Runde 2

### N-B1 — die Lead-SKILLs behaupteten eine Mechanik, die dieses Paket nicht baut

**Gemessen in diesem Baum:** `grep -rn "rung" team-kits/kernel/*.py` → kein Treffer; die
Verfassungen sagen an b7f282e `Escalation ladder (user-gated, triggered by the FIRST QA fail …):
sonnet-high → … → opus-xhigh/max` (dev um Zeile 375, research um 348). Meine erste Fassung sagte das
Gegenteil und nannte den Absatz daneben „the whole rule".

**Gebaut:** der SKILL-Schritt haelt jetzt **keine Kopie**. Er sagt, wo die Regel lebt, und nichts
darueber, was sie sagt — die einzige Fassung, die in **beiden** Baeumen wahr ist. Der Waechter heisst
jetzt `test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule` und liest die **Behauptung** statt
einer Tokenform: ein `<Sprosse>-<Effort>`-Schritt, **oder** die Woerter des abgeloesten Mechanismus
(`user-gated`, „first QA fail", „first validation FAIL", „user-confirmed only"), **oder** ein Satz,
der dem Lead erzaehlt, was der KERNEL ableitet. Dazu die zweite Haelfte, die der Pruefer verlangt
hat: der Zeiger wird **verfolgt** — der Absatz muss in der Verfassung dieses Kits wirklich stehen.
Der Docstring sagt jetzt, was an b7f282e wirklich in den Verfassungen steht.

Mutationen: alte Regel als **Prosa** zurueck → RED; „der Kernel leitet ab" → RED; Zeiger weg → RED;
Tokenform zurueck → RED; Verfassungsabsatz weg (beide Nennungen) → RED; `work`-Klausel weg → RED.

### N-B2 — vier Leer-Schreibweisen von `work` kamen durch und schwiegen die Warnung

**Gebaut:** zwei Praedikate in `backlog_types`, beide Enden fragen dasselbe.
`work_is_none` ist **genau** der Skalar `none` (DEC-0083 (2)(c) nennt eine Stille);
`work_is_stated` ist „die eine Stille **oder** `names_something`". Die Tuer (`cli.capture`) und der
Validator (`_check_decision_carriers`) rufen sie; ein leeres `work` ist jetzt derselbe Zustand wie
ein fehlendes, und `["none"]` ist eine Id wie jede andere (also ein Fehler, wenn sie niemand traegt).

**Gemessen, je Schreibweise, an beiden Enden:** `{}`, `[]`, `""`, `[""]`, `"   "`, `[[]]`, `[None]`
→ rc 1 an der Kommandotuer und **warning** im Validator; `none` → rc 0 und still; `["none"]` → rc 0
und **error**. Fuenf Mutationen, alle RED (`work_is_none` akzeptiert jedes Leere, `work_is_stated`
verliert die `names_something`-Haelfte, der Validator liest Leeres als Antwort, die Tuer faellt auf
Schluessel-Anwesenheit zurueck, der `none`-Eintrag in einer Liste wird uebersprungen).

## N11. N-B3 — `migrate.py` liegt nicht in meinem Bereich: der Hunk ist ZURUECKGENOMMEN

`team-kits/kernel/migrate.py` steht in **keinem** der fuenf Kernel-Eintraege des `allowed_scope`.
Mein Hunk (ein Feld + fuenf Zeilen Kommentar, davon ein falscher Klammersatz ueber
`capture_preflight`) ist **vollstaendig zurueckgenommen**; `git diff` nennt die Datei nicht mehr.

**Folge, gemessen:** die Quittung des Migrationslaufs (`migrate.RECEIPT_TYPE == "DEC"`) traegt damit
kein `work`, und der neue Validator nennt sie zu Recht „decision without a carrier" — acht
Zusicherungen in `tools/test_migrate.py` verlangten „gar keine Befunde". Sie sagen jetzt **beim
Namen**, welche eine Warnung sie zulassen (`findings_beside_the_receipts_carrier`, ein Filter, der
nur diese eine Meldung fuer genau die Quittung dieses Laufs faellt und jede andere durchlaesst).
Danach: `tools/test_migrate.py` **141 passed**.

**Naht an den Merge (eine Zeile):** in `_receipt_fields` (`team-kits/kernel/migrate.py`) gehoert
`DEC_WORK_FIELD: DEC_WORK_NONE` in das `fields`-Dict, mit dem Grund „die Quittung haelt fest, was ein
Lauf GETAN hat; sie entscheidet nichts, das jemand bauen muesste". Danach faellt der Filter oben weg.
Wer den Bereich weitet, entscheidet der Lead.

## N12. Nutzerentscheidung zum Schliessweg (aufgenommen)

Der Nutzer hat `dec-bug-closing-route.json` mit **Option A** beantwortet, festgehalten als
**`DEC-0086`**: Muenzung je Bug, in einem Zug, vom Lead relayt. Damit gilt fuer AC-1/AC-6 der ausgelieferte Weg
(`("BUG","scope"): ("TRIAGED","APPROVED")`), und der Strom hat alles vorbereitet, was ohne den Klick
geht: die bestaetigende Evidenz liegt (EVD-0086..0090), die nachgemessenen Ketten stehen in den
Items, und die sechs Zeilen stehen in Abschnitt 6. `DEC-0086` traegt seit dieser Runde `work: [TSK-0131]`.
**Erledigt waehrend dieser Runde, nicht von mir:** der Lead hat die fuenf Muenzungen gefahren --
`BUG-0025/0033/0088/0090/0091` stehen **VERIFIED und archiviert**. `BUG-0069` bleibt offen und
wartet auf den gehosteten Lauf nach dem Merge-Push.

## N13. Nahttabelle, erweitert

| Datei | Was der Merge tun muss |
|---|---|
| `team-kits/{dev,research}-team/skills/project-manager/SKILL.md` | G5-2s Satz **nachtragen**, wenn seine Mechanik landet. Wortlaut, wie G5-2 ihn in die Verfassungen geschrieben hat: „**What you do with it:** when the header's `rung` is not the role's own pin, pass it as the Agent call's `model:` — the spawn gate refuses any spawn whose `model` is not the rung, a higher one included." Dieser Strom darf ihn nicht schreiben: in **diesem** Baum gibt es weder `rung` noch das Gate, und ein SKILL, der eine Datei oder ein Kommando seines eigenen Kits nennt, das es nicht gibt, ist rot (`tools/test_hooks.py::test_instruction_files_name_only_state_files_a_v2_project_has`, `::test_every_command_a_role_is_handed_is_on_the_entry_points_surface` — beide haben genau das gemeldet). |
| `tools/test_model_ladder.py` (G5-2) | die zwei Lead-SKILL-Eintraege aus `STALE_LADDER_TEXTS` **entfernen** (nach dem Merge tot; die Karte wird an beiden Enden gemessen). Die drei `templates/project_memory/project_config.yaml` bleiben — `templates/**` ist verbotener Bereich dieses Stroms. |
| `team-kits/kernel/migrate.py` | `DEC_WORK_FIELD: DEC_WORK_NONE` in `_receipt_fields` (N11), danach den Filter in `tools/test_migrate.py` entfernen. |
| `docs/POST_V2_WISHLIST.md` | nach dem letzten Loch einmal `migrate-holes --reindex` (in dieser Runde dreimal gefahren, zuletzt 175 Loecher). |

## N14. Suiten der Nacharbeit 2

| Auswahl | Ergebnis |
|---|---|
| `tools/test_migrate.py` | **141 passed in 202.04s** |
| `test_report.py` (Traeger + Tuer, gezielt) | 2 passed |
| `test_review_procedure.py` (Leiter + `work`-Klausel, gezielt) | 2 passed |
| `test_backlog_types, test_kernel, test_parallel_scopes, test_report, test_state, test_staging_cli, test_migrate_holes, test_pointer_sweep, test_schemas, test_board, test_review_procedure, test_role_contracts, test_reference_skills, test_parallel_streams, test_approvals_dispatch` | **905 passed, 2 failed in 371.87s** -- beide Rot sind die Store-Naht (`DEC-0080`/`DEC-0083` liegen im Hauptstore) |
| `test_hooks, test_hooks_v2, test_migrate, test_repo_hygiene, test_context_budget` | **3358 passed, 13 skipped, 1 failed in 35:03** -- das eine Rot ist dieselbe Naht (`DEC-0083` in einer Kit-Datei zitiert) |
| Merge-Sicht: die vier Naht-Tests | **4 passed** |

## N15. Stempel, Patch und Uhr der Nacharbeit 2

`bump_kit_version.py` nach jeder Kit-Aenderung; der gueltige Stempelstand steht **einmal**, in N20
(je Kit gelesen -- die Zaehler laufen pro Kit und nicht gemeinsam).
`ruff check .`: All checks passed. `tools/validate.py`: all structural checks passed.
**Korrigiert (R3-1):** hier stand `0 error(s), 67 warning(s)`, gemessen mit dem Kernel, den dieses
Paket **ersetzt**. Die Zahl des **laufenden** Kernels steht **einmal**, mit gelesener Uhr, in
**N20** -- sie wandert mit jedem Kernel-Schreiben des Leads, und zwei Fassungen davon in einer
Datei sind genau der Defekt, den diese Runde an anderer Stelle gemeldet bekam.

**Patch:** `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0131/stream-stock.patch` -- **37
Dateien**, keine VERSION-, keine `project_memory/`- und **keine `team-kits/kernel/migrate.py`**-Hunks
mehr; `git apply --check` gegen einen sauberen b7f282e **rc 0**.

**Neue/geaenderte Items dieser Nacharbeit:** `BUG-0268` (H185, CLAUDE.md nennt vier Gates -- als
LOCH neu erfasst, weil die erste Fassung ein einfacher BUG war und im Zeigerindex nicht auftauchte);
`BUG-0267` **DUPLICATE**, archiviert; Zeigerindex neu geschrieben (175 Loecher).

**Uhr (gelesen):** Nacharbeit 2 von 10:47 bis 15:32, rund **4 h 45 min**, davon etwa 50 min
Suitenlaeufe und 35 min der grosse Haken-Lauf. Zusammen mit Runde 1 und Nacharbeit 1: rund **10 h**
Wandzeit dieses Umsetzers. **Token:** dieser Prozess kann seinen eigenen Verbrauch nicht lesen.


---

# Runde 4 (Abschluss, nach Pruefrunde 3) — 2026-09-06

## N16. Die beiden Befunde der Runde 3

### N3-B1 — der Quittungs-Filter verwarf die Warnung fuer JEDE Entscheidung

`findings_beside_the_receipts_carrier` las `iter_active_items(migrate.RECEIPT_TYPE)`, und
`RECEIPT_TYPE == "DEC"` — also jedes aktive Entscheidungsitem. Der Docstring versprach das Gegenteil
(„any other finding -- including a second decision without a carrier -- comes through“), und zehn
`assert not findings` dieser Suite massen damit nichts.

**Gebaut:** die Quittung wird an ihrer **Identitaet** erkannt — dem `source`, den
`migrate._receipt_fields` selbst schreibt, ausgelesen aus der Funktion statt hier getippt
(`_receipt_source_prefix`). **Neuer Test:** nach einem echten Import stehen eine Quittung und eine
handgeschriebene traegerlose Entscheidung im Store; der Filter laesst genau die zweite durch.
Mutationen: Filter faellt auf den Typ zurueck → **RED**; Praefix auf einen Wert gesetzt, den keine
Quittung traegt → **RED**.

**Und ein zweites Rig-Artefakt derselben Familie**, beim Messen gefunden: `test_migrate` stellt sein
V1-Fixture aus der **git-Historie** dieses Repos wieder her, und die Rig-Kopie hatte keine. Die
ersten beiden Laeufe meldeten `1 error` — wieder ein Rot, das nichts ueber die Mutation sagt. Das Rig
kopiert fuer solche Faelle jetzt die `.git`-**Zeigerdatei** (die Tests lesen nur: `log`, `show`), und
ich habe gemessen, dass das den Hauptcheckout nicht anfasst: `git status --porcelain` davor und
danach identisch.

### N3-B2 — die Zeiger-Haelfte folgte dem Zeiger nicht

Sie akzeptierte **jeden** Fettabsatz, in dem das Wort `ladder` vorkam — zwei taten das, einer nur
beilaeufig, also blieb sie gruen, wenn man den echten Absatz loeschte.

**Gebaut:** der Absatz wird daran erkannt, **was er traegt** — eine Sprosse *als Wert* (ein Codespan,
der mit dem Sprossennamen beginnt) **und** ein Effort-Wert —, und es muss **genau einer** sein.
Gemessen ueber **beide** Baeume: in diesem Paket qualifiziert `- **Effort:** all high … sonnet-high
→ …`, in G5-2s Fassung `- **The ladder is BUILT, not prose …** three rungs `sonnet < opus < fable``
— je genau einer, also ueberlebt der Leser die Ersetzung. Zwei Fallen dabei selbst gemessen und
geschlossen: das Sprossen-Vokabular kam aus **allen** Strings von `model_tiers.yaml` (also auch
`effort`, wodurch ``effort: high`` als Sprosse las) und `fable` fehlte darin ganz.
Mutationen: der Absatz verliert die Sprossenangabe → **RED**; eine **zweite** Regel-Absatz kommt
dazu → **RED**.

## N17. Die Reste der Runde 3

| Rest | Erledigt als |
|---|---|
| **R3-1** N15-Zahlen vom alten Kernel | oben korrigiert; die Zahl des laufenden Kernels steht **einmal**, in N20 (mit gelesener Uhr und der Liste der traegerlosen Entscheidungen) |
| **R3-2** `DEC-0086` ohne `work`, N12 ohne Id | `work: [TSK-0131]` geschrieben, N12 nennt die Id; `DEC-0085` bekam `work: [TSK-0130]` |
| **R3-3** Tabelle dem Store hinterher | neu **aus dem Store** erzeugt; der Abgleich wurde in der Abschlussrunde noch einmal gefahren und steht mit seinen Zahlen in N20 |
| **R3-4** `work` nahm eine Entscheidung als Traeger | eine Zeile in `_check_decision_carriers`: ein `work`-Ref, der ein `DEC` ist, ist ein **Fehler** („a decision is not a carrier“) — beide Richtungen der Pruefung sagen jetzt dasselbe. Mutation RED |
| **R3-5** `work: 'NONE'` kommt durch die Tuer | die Tuermeldung sagt jetzt „**that exact word, lower case**“ |
| **R3-6** Naht fehlt in N13 | unten in N18 nachgetragen |
| **R3-7** vier reparierte Bugs standen `OPEN` | **erledigt vom Lead**: alle fuenf sind VERIFIED und archiviert |

**Was ich NICHT geschrieben habe, und warum:** acht der neun traegerlosen Entscheidungen
(`DEC-0005/0007/0023/0035/0037/0052/0054/0058`) haben kein `work` bekommen. Sie stammen aus der Zeit
**vor** Generation 4; `DEC-0083` (5) nennt ausdruecklich die Entscheidungen der Generationen 4/5, und
welchen Traeger eine dieser acht hat, sagt weder ihr Titel noch der Store — das ist je eine Lektuere,
kein Feldwert, den ich raten darf. `DEC-0049` („Board page and office archive folder names stay
ENGLISH“) ist die eine, die sich ohne Lektuere entscheiden laesst: eine Benennungsregel verpflichtet
niemanden, also `work: none`.

## N18. Nahttabelle, letzter Stand

| Datei | Was der Merge tun muss |
|---|---|
| `team-kits/{dev,research}-team/skills/project-manager/SKILL.md` | G5-2s Satz nachtragen, wenn seine Mechanik landet: „**What you do with it:** when the header's `rung` is not the role's own pin, pass it as the Agent call's `model:` — the spawn gate refuses any spawn whose `model` is not the rung, a higher one included.“ Dieser Strom darf ihn nicht schreiben (weder `rung` noch das Gate existieren hier). |
| **NEU (R3-6)** `dev-team` + `research-team` `constitution/AGENTS.md` | Mein Waechter verlangt **genau eine** fettgefuehrte Aussage, die die Regel **in sich selbst** traegt (seit N21/N4-2: der Subjektblock endet am naechsten Listenpunkt oder an der Leerzeile, **nicht** erst an der naechsten Fettfuehrung) — eine **Sprosse als Wert** (Codespan, der mit dem Sprossennamen beginnt) **und** den **Feldnamen** der Effort-Achse, wie `team-kits/model_tiers.yaml` ihn nennt (`effort_field`, heute `effort`) —, und im SKILL die Zeichenkette `constitution's ladder paragraph`. **Nicht in jeder Verfassung:** die Bedingung greift nur, wo das Lead-SKILL ueberhaupt ueber Skalierung spricht; das office-SKILL tut es nicht, und gemessen qualifiziert in `office-team` **0 von 27** Absaetzen, waehrend der Test gruen ist (dev 1/35, research 1/35 — `rung_read.py`). G5-2 **ersetzt** genau diesen Absatz. **Gemessen woran:** an dem Absatztext, den G5-2s Protokoll zitiert („three rungs `sonnet < opus < fable` … effort **high** by default“) — er qualifiziert, die Naht haelt. G5-2s **Baum** lag mir nicht vor; wer den Absatz umschreibt, muss die zwei Achsen kennen. |
| `tools/test_model_ladder.py` (G5-2) | die zwei Lead-SKILL-Eintraege aus `STALE_LADDER_TEXTS` entfernen; die drei `project_config.yaml` bleiben (`templates/**`, verbotener Bereich). |
| `team-kits/kernel/migrate.py` | `DEC_WORK_FIELD: DEC_WORK_NONE` in `_receipt_fields`; danach faellt `findings_beside_the_receipts_carrier` in `tools/test_migrate.py` weg. |
| `docs/POST_V2_WISHLIST.md` | nach dem letzten Loch einmal `migrate-holes --reindex`. |

## N19. Die (g)-Zeile dieses Stroms

| Feld | Wert |
|---|---|
| Stufe | **Opus 5, effort high** (`DEC-0081`) |
| Runden | **1 Bericht + 2 Nacharbeiten + 1 Abschlussrunde**, **4 Verifikationen** (FAIL/FAIL/FAIL/die vierte laeuft ueber diese Abschlussrunde) |
| Wandzeit (Uhr gelesen, `date`) | Vorgaenger auf Fable 2026-09-05 21:21–22:07; **Umsetzer A** (Runde 1 + Nacharbeiten 1/2 + Runde 4) 2026-09-05 22:10:46 bis 2026-09-06 16:53 — rund **14 h**, davon grob **5 h** Suiten- und Rig-Laeufe; **Umsetzer B** (dieser Prozess, Uebernahme nach der Unterbrechung) 2026-09-06 **17:10:51** bis **N20** |
| Token (Umsetzer) | **A: ~896 k** (Zahl des Leads aus dem Spawn-Protokoll, hier nicht nachgemessen). **B: siehe N20 (g)** — aus dem eigenen Zaehler gelesen, nicht geschaetzt. |
| Token (Pruefer) | **Runde 4: ~165 k** (eigener Zaehler des Pruefers, `verify-round-4.md`: 14 966 890 → 14 801 683 um 19:47). **Runden 1–3: nennen ihre Zahl nicht** — die drei Berichte fuehren keine; nachtragen kann sie nur der Lead aus dem Spawn-Protokoll, und geschaetzt wird hier nichts. |
| Eigene Befunde | der veraltete Loch-Tabellen-Test (rot auf **jedem** Lauf ab b7f282e und in der CI beider Plattformen), der tote Zeigerindex fuer 15 Loecher, `stock_rollup` als Statusschreiber, die Kommandolisten-Pflicht, der `DEC_FIELDS`-Shadow, die V1-Import-Kollision der `work`-Tuer, **zwei Rig-Artefakte** (fehlender Neustempel, fehlende git-Historie), die typisierte Sprossen-Liste `("fable",)` hinter einer Schutzbehauptung; **Umsetzer B:** der Zeiger auf eine Rig-Datei im Scratch als Beleg in einer ausgelieferten Docstring und der Bereich des Zeiger-Sweeps (`BUG-0270`/H187) |
| Verifiziererbefunde | 4 + 3 + 2 blockierende, dazu 9 + 7 Reste — alle geschlossen oder benannt |
| Naehte | G5-2 (SKILL-Satz, `STALE_LADDER_TEXTS`, der Verfassungsabsatz), `migrate.py`-Zeile, `migrate-holes --reindex` |
| Wartet auf den Nutzer | **nur noch `BUG-0069`** — der gehostete Lauf nach dem Merge-Push ist die Evidenz. (Die vier Lieferfreigaben sind erteilt: `PR-0004..0007` stehen **DELIVERED**, gemessen 2026-09-06 18:26 im Store.) |
| Neue Items | `BUG-0256`/H174 (DUPLICATE, archiviert), `BUG-0257`/H175, `BUG-0261`/H179, `BUG-0262`/H180, `BUG-0265`/H183, `BUG-0268`/H185, **`BUG-0270`/H187**; `BUG-0267` DUPLICATE (archiviert). Stand je Item gemessen 2026-09-06 18:26 (`items_claim.py`). |

---

# Abschlussrunde (Umsetzer B, nach der Unterbrechung) — 2026-09-06

Uhr gelesen (`date`): Beginn **17:10:51**. Dieser Prozess ist ein **anderer Agent** als Umsetzer A;
er hat nichts vorausgesetzt, sondern zuerst gemessen, welchen Stand die Abschlusszeile erreicht
hatte.

## N20. Was gemessen wurde, und was daran noch falsch war

### (a) Der vorgefundene Stand — gemessen, nicht angenommen

| Was | Messung |
|---|---|
| Arbeitsbaum `g5-stock` | 41 geaenderte/neue Dateien; die Runde-4-Aenderungen gegen die Pruefer-Kopie `verify/r3` sind genau sechs: `kernel/cli.py`, `kernel/report.py`, `tools/test_migrate.py`, `tools/test_report.py`, `tools/test_review_procedure.py` und die drei `VERSION` |
| Abgebrochener Lauf `round5-suites.log` | 16:53 mitten im Lauf getoetet, drei Rot darin — **alle drei identifiziert** (unten (c)), kein unbekannter Rueckschritt |
| `stream-stock.patch` (16:21) | **veraltet** gegenueber den Aenderungen von 16:28–16:38; neu erzeugt (unten (f)) |

### (b) Die beiden Befunde der Pruefrunde 3 — gebaut vorgefunden, von mir rot-zuerst nachgemessen

Rig `redfirst.py` (kopiert den Arbeitsbaum, mutiert **eine** Sache, stempelt bei Kit-Mutationen neu,
faehrt **eine** Auswahl), 12 Faelle, **jeder RED** — Lauf `r4-redfirst.log`, 2026-09-06 18:25–18:27:

```
receipt-filter-drops-every-decision                        RED  1 failed, 1 passed
receipt-prefix-read-from-a-typed-string                    RED  2 failed
work-accepts-a-decision-as-a-carrier                       RED  1 failed, 1 passed
constitution-loses-the-paragraph-that-states-the-rule      RED  1 failed, 1 passed
constitution-grows-a-second-paragraph-that-states-the-rule RED  1 failed, 1 passed
ladder-paragraph-loses-the-effort-axis                     RED  1 failed
tier-table-states-no-effort-vocabulary                     RED  2 failed
a-kit-agent-carries-an-unstated-effort                     RED  1 failed
tier-table-names-no-effort-field                           RED  1 failed
rung-derivation-drops-the-half-that-reaches-the-top        RED  1 failed, 1 passed
tier-file-no-longer-names-the-top-rung                     RED  1 failed
a-kit-agent-pins-a-model-the-vocabulary-cannot-reach       RED  1 failed
```

Die Ausgangslage dazu ist der gruene Lauf aus (c): dieselben Auswahlen sind ohne Mutation gruen.

**N3-B1** ist in **beiden** Richtungen gehalten, und das ist der Punkt. Welcher Test in Fall 1
faellt, sagt die Schlusszeile des Rigs nicht — also einzeln nachgemessen (`redfirst_verbose.py`,
19:00):

```
PASSED tools/test_migrate.py::test_the_migrated_state_passes_the_validator
FAILED tools/test_migrate.py::test_the_receipt_filter_drops_the_receipt_and_nothing_else
```

Faellt der Filter auf den TYP zurueck, verwirft er jede Traeger-Warnung — die alte Zusicherungsstelle
bleibt **gruen** und nur der neue Test wird rot. Genau der Fall, den die Suite vorher nicht sehen
konnte. Fall 2 (Praefix aus einer getippten Zeichenkette, der Filter trifft nichts) macht **beide**
rot. Das ist die Behauptung, die jetzt in der Docstring der Funktion steht.

**N3-B2:** die zwei Achsen des Absatzes sind einzeln gemessen (Sprosse weg → rot, Effort-Achse weg →
rot — **die zweite Zeile stimmte hier nur mit einer zusaetzlichen Aenderung; das ist der Befund
N4-2 der Pruefrunde 4, korrigiert in N21**), die Eindeutigkeit ebenfalls (zweiter Regel-Absatz →
rot), und die Ableitung darunter an
beiden Enden (Tier-Datei nennt die oberste Sprosse nicht mehr → rot; ein Kit pinnt ein Modell, das
die Ableitung nicht erreicht → rot). Gemessen (`rung_read.py`): Sprossen-Vokabular
`fable, haiku, lead, light, opus, sonnet, worker`, Effort-Vokabular `high, low, max, medium, xhigh`,
Effort-Feld `effort`; qualifizierende Absaetze **dev 1/35, research 1/35, office 0/27** — office
traegt keinen und braucht keinen, weil sein Lead-SKILL nicht ueber Skalierung spricht.

### (c) Die drei roten Tests des Arbeitsbaums sind die STORE-NAHT, nichts sonst

```
18 lesende Suiten (Arbeitsbaum)   3 failed, 1122 passed in 1664.36s (27:44)
  test_review_procedure::test_every_item_pointer_the_harness_role_texts_write_resolves
  test_review_procedure::test_the_harness_role_texts_carry_the_generation_4_rules_with_their_pointers
  test_repo_hygiene::test_every_decision_pointer_in_a_shipped_kit_file_resolves
dieselben drei in der MERGE-SICHT (dieser Code ueber einer Kopie des heutigen Hauptstores)
                                  3 passed in 35.15s   (`mergeview_r4.py`)
```

Der Arbeitsbaum traegt `project_memory/` im Stand b7f282e; `DEC-0080`, `DEC-0083`, `TSK-0131` und
`BUG-0251` liegen im Hauptstore. Der dritte war der bis dahin unerklaerte Rote aus dem
abgebrochenen Lauf.

### (d) Was ich SELBST gefunden habe — und was davon eine Korrektur brauchte

1. **Ein Beleg, der auf eine Datei im Scratch zeigt.** `tools/test_migrate.py` begruendete seine
   Verengung mit „the mutation that proves it is `redfirst.py::receipt-filter-drops-every-decision`".
   `redfirst.py` liegt im Runden-Scratch und wird beim Rundenabschluss geloescht — der Beleg zeigt
   dann auf nichts, in einer Datei, die bleibt. **Geaendert:** die Docstring nennt jetzt den
   Geschwister-Test derselben Datei, der die Behauptung wirklich haelt, und sagt, dass er in
   **beiden** Richtungen faellt (oben gemessen). Die Mutation steht hier im Protokoll, wo eine
   Rundenmessung hingehoert. **Ohne diese Aenderung wird kein Test rot** — und genau das ist der
   zweite Befund.
2. **`BUG-0270` / `H187`, neu erfasst mit `limits`:** der Zeiger-Sweep dieses Repos liest zwei
   Baeume — gemessen mit seinem eigenen Leser (`sweep_subject.py`): `['docs', 'team-kits']`,
   **480** gepruefte Zitate. Ueber `tools/*.py` stehen weitere **39** Testzeiger, die er nie
   oeffnet; **4** davon loesen heute an nichts auf, und alle vier sind Fixture-Zeichenketten in
   `tools/test_pointer_sweep.py` — Illustrationen, die Klasse aus `H175`. Deshalb ist die Luecke
   **benannt und nicht geschlossen**: den Bereich heute zu verbreitern faerbt vier Illustrationen
   rot, und die Unterscheidung Illustration/Zeiger ist `H175` (`BUG-0257`).
3. **Eine falsche Behauptung ueber `.gitattributes`** in Abschnitt 12 (die Rollendefinitionen
   fehlten angeblich in `git archive`) — zurueckgenommen, mit der Messung an ihrer Stelle.
4. **Vier veraltete Behauptungen im eigenen Protokoll**, korrigiert statt stehen gelassen: N18 sagte
   „in **jeder** Kit-Verfassung" (gemessen: nur dort, wo das Lead-SKILL ueber Skalierung spricht) und
   „einen Effort-**Wert**" (gebaut ist der **Feldname**); Abschnitt 6 und Abschnitt 9 fuehrten
   Erledigtes als offen; N15 nannte einen Sammel-Stempel, den die drei Kits nicht teilen.

### (e) Die Reste der Pruefrunde 3, mit der Messung von heute

| Rest | Stand |
|---|---|
| **R3-1** Validator-Zahlen | **Gemessen 2026-09-06 18:24, Kernel dieses Pakets gegen den Hauptstore: `0 error(s), 77 warning(s)`, davon `10` „decision without a carrier"** — `DEC-0005/0007/0023/0035/0037/0052/0054/0058` (vor Generation 4; welchen Traeger eine von ihnen hat, sagt weder Titel noch Store — das ist je eine Lektuere, kein Feldwert, den ich raten darf) sowie **`DEC-0087`/`DEC-0088`**, heute vom Lead erfasst (die leichte Arbeitsform, ihre Stufen und ihr Takt): **ihr Traeger ist das Ziel der Generation 6**, das es noch nicht gibt, also bleiben sie bewusst ohne `work`. `DEC-0085` traegt `[TSK-0130]`, `DEC-0086` `[TSK-0131]`, `DEC-0049` `none`. Die Zahl steht **nur hier**, weil sie mit jedem Kernel-Schreiben des Leads wandert |
| **R3-2** `DEC-0086` ohne `work`, N12 ohne Id | erledigt (Store nachgesehen), N12 nennt die Id |
| **R3-3** Tabelle gegen Store | **neu erzeugt und abgeglichen 18:29 (`recon_table.py`): 199 Zeilen = 199 aktive BUG-Items, `in table not active` leer, `active not in table` leer, 0 Standabweichungen.** 197 → 199, weil heute zwei Loecher dazukamen: `BUG-0269`/H186 (Lead) und `BUG-0270`/H187 (dieser Bericht). Beide stehen als `UNMEASURED` — kein Test nennt sie, und genau das meint das Vokabular der Tabelle |
| **R3-4** Entscheidung als Traeger | gebaut (Fehlerzeile im Validator), Mutation `work-accepts-a-decision-as-a-carrier` **RED** |
| **R3-5** `NONE` durch die Tuer | die Tuermeldung sagt „that exact word, lower case" |
| **R3-6** Naht in N13/N18 | nachgetragen und in dieser Runde praezisiert (oben (d) 4) |
| **R3-7** vier Bugs standen `OPEN` | erledigt vom Lead: `BUG-0025/0033/0088/0090/0091` **VERIFIED und archiviert**, `PR-0004..0007` **DELIVERED** — im Store nachgesehen (`items_claim.py`, 18:26) |

### (f) Suiten dieser Abschlussrunde — und WARUM diese (DEC-0080 (2))

Die geaenderte Regel ist `report.validate_state` (Runde 4 haengt `_check_decision_carriers` eine
Fehlerzeile an). Ihre Leser, per `grep -ln validate_state` ueber die Suiten ermittelt:
`test_backlog_types`, `test_hooks`, `test_hooks_v2`, `test_kernel`, `test_migrate`,
`test_parallel_scopes`, `test_report` — **alle sieben sind gelaufen**. `.claude/hooks/test_gates.py`
steht in derselben grep-Liste, **nennt** `validate_state` aber nur in einer Docstring und ruft es
nicht auf (nachgelesen); seine Loch-Leser sind trotzdem gefahren, weil diese Runde ein Loch erfasst
und den Index neu gerendert hat.

| Auswahl | Ergebnis | Wann |
|---|---|---|
| 18 lesende Suiten (`test_backlog_types, test_kernel, test_parallel_scopes, test_report, test_state, test_staging_cli, test_migrate_holes, test_pointer_sweep, test_schemas, test_board, test_review_procedure, test_role_contracts, test_reference_skills, test_parallel_streams, test_approvals_dispatch, test_migrate, test_repo_hygiene, test_context_budget`) | **3 failed, 1122 passed in 1664.36s** — die drei sind die Store-Naht (c) | 17:53–18:21 |
| `tools/test_hooks.py` | **1006 passed, 13 skipped in 2232.90s** (37:12) — darin der Kit-Audit, der die Spiegelung byte-identisch haelt | 17:16–17:53 |
| `tools/test_hooks_v2.py` | **2138 passed in 1654.88s** (27:34) | 18:28–18:55 |
| Merge-Sicht: die drei Naht-Tests | **3 passed in 35.15s** | 18:22 |
| Merge-Sicht: die vier Loch-Leser (`test_repo_hygiene` Triple + drei aus `test_gates.py`) | **3 passed, 1 failed in 25.67s** — der eine Rote ist **fremd**: `H169`/`H171` (`BUG-0251`/`BUG-0253`, von G5-2 erfasst) nennen Tests aus `tools/test_ladder.py`, die G5-2 baut und mein Baum nicht hat. Loest sich beim Merge auf | 18:56 |
| Rig `redfirst.py`, 12 Mutationen | **12 × RED** (oben (b)) | 18:25–18:27 |

**Gate 5:** keine Vollflaechen-Zeile; jeder Lauf nennt seine Dateien. Die volle Suite gehoert dem
Merge. **Host-Regel:** immer nur **ein** pytest gleichzeitig, jeder Lauf mit `timeout`.

### (g) Stempel, Patch, Uhr, Token

**Stempel** (`python tools/bump_kit_version.py`, 18:28 gelaufen — **unchanged**, weil diese
Abschlussrunde keine Kit-Datei angefasst hat; die einzige Code-Aenderung ist eine Docstring in
`tools/test_migrate.py`): **dev-team `2026.09.06-9`, office-team `2026.09.06-8`, research-team
`2026.09.06-10`**. Die drei Zaehler laufen **pro Kit** — der frueher hier stehende Sammelwert war
falsch. `python -m ruff check .`: **All checks passed** (18:29). `python tools/validate.py`: **all
structural checks passed** (18:29).

**Patch:** `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0131/stream-stock.patch`, neu erzeugt
18:29 (`patch_make.py`, schreibt **binaer**):

```
(neu geschnitten 20:07 nach der Nachbesserung N21)
patch bytes=258531  files=37  CRLF lines=0
hunks naming VERSION 0 · project_memory 0 · CLAUDE.md 0 · .claude/hooks 0 · settings.json 0 ·
             team-kits/kernel/migrate.py 0 · templates/ 0 · /hooks/ 0 · model_tiers 0
git apply --check gegen `git archive b7f282e` in einem Wegwerf-Repository: rc=0
```

Alle 37 Pfade liegen im `allowed_scope` des Auftrags. Kein Commit, kein Push, keine Installation in
den globalen Speicher.

**Uhr (gelesen, `date`):** Umsetzer B von **17:10:51** bis **18:59:09** — rund **1 h 50 min**, davon
etwa **1 h 35 min** Suiten- und Rig-Laeufe (37:12 + 27:44 + 27:34 + 2 Merge-Sichten + 12
Rig-Faelle). Zusammen mit Umsetzer A und dem Fable-Vorgaenger: die Zeile in N19.

**Token:** Umsetzer A **~896 k** (Zahl des Leads, hier nicht nachgemessen). **Umsetzer B: 287 k**,
aus dem eigenen Zaehler dieses Prozesses gelesen — verbleibendes Budget **14 965 917** bei Beginn
(17:10) gegen **14 678 860** nach der Nachbesserung N21 (20:08); der Bericht an den Lead kommt noch
dazu. **Pruefer Runde 4: ~165 k** (dessen eigener Zaehler, `verify-round-4.md`); die Pruefrunden
1–3 nennen keine Zahl.

### (h) Was diese Runde bewusst NICHT geschlossen, sondern benannt hat

| Als was | Was, und warum offen |
|---|---|
| **`BUG-0270` / `H187`** | Der Zeiger-Sweep liest `tools/` nicht (39 ungelesene Zeiger). Zuerst braucht es `H175`: heute wuerden vier **Illustrationen** rot |
| ohne Item, hier benannt | **Acht traegerlose Entscheidungen vor Generation 4** (`DEC-0005/0007/0023/0035/0037/0052/0054/0058`) bekommen kein `work` von mir: welchen Traeger eine hat, sagt weder ihr Titel noch der Store — das ist je eine **Lektuere**, kein Feldwert, den ich raten darf |
| ohne Item, hier benannt | **`DEC-0087`/`DEC-0088`** (heute erfasst) bleiben ohne `work`: ihr Traeger ist das **Ziel der Generation 6**, das es noch nicht gibt. Ein `work: none` waere die falsche Antwort — sie verlangen sehr wohl Arbeit |
| Nutzerzeile | **`BUG-0069`** wartet auf den **gehosteten Lauf** nach dem Merge-Push; das ist die Evidenz, die es schliesst |
| Naht, kein Defekt | Der eine fremde Rote der Merge-Sicht (`H169`/`H171` → `tools/test_ladder.py` aus G5-2) |
| Grenze der eigenen Messung | Die Aussage „G5-2s Absatz qualifiziert" ist an dem **Text** gemessen, den G5-2s Protokoll zitiert — **nicht** an dessen Baum, der mir nicht vorliegt |

## N21. Die vier Befunde der Pruefrunde 4 (Prosa gegen Code) — 2026-09-06, 19:53–20:10

Kein fuenfter Durchgang ueber das Paket (`DEC-0088` (c)): vier Zeilen, rot-zuerst wo der Fix ein
Test ist, danach neuer Patch. Der **Merge-Pruefer** misst sie am gemergten Baum.

### N4-1 — „and nothing else" war auf das ITEM verengt, nicht auf die Meldung

Die Zusicherung las nur Meldungen mit `without a carrier`, also haette ein Filter, der **jeden**
Befund ueber die Quittung verwirft, sie erfuellt. **Entschieden: die Zeile bauen, nicht den Satz
zuruecknehmen** — der Satz ist die Eigenschaft, die die zehn `assert not findings` dieser Suite
ueberhaupt tragfaehig macht; ihn zurueckzunehmen hiesse, den Filter als „irgendwie enger" stehen zu
lassen. Gebaut: nach dem Import bekommt die Quittung einen **zweiten** Befund ueber sich selbst
(`supersedes: [DEC-9999]`, also `report._check_dec_supersedes` und nicht die Traegerzeile), und der
muss durchkommen.

```
tools/test_migrate.py::test_the_receipt_filter_drops_the_receipt_and_nothing_else   1 passed in 9.63s
Mutation receipt-filter-drops-every-finding-about-the-receipt  RED  1 failed, 1 passed
   (vor dieser Zeile: GREEN, 142 passed — die Messung des Pruefers)
tools/test_migrate.py (ganze Suite)                                142 passed in 474.69s
```

### N4-2 — „exactly ONE bold paragraph" war ueber die SPANNE gebaut

`_lead_in_units` schneidet erst an der naechsten Fettfuehrung; der Ladder-Punkt der dev-Verfassung
zog damit zehn Zeilen mit, darunter den Punkt „- The scaffold stamps Claude `model:`/`effort:`
frontmatter". Dessen `effort:` hielt die Aussage qualifiziert, nachdem ihre **eigene** Achse weg
war. **Entschieden: den Leser wahr machen, nicht den Satz** — ein Absatz, der die Regel traegt, ist
das, worauf das SKILL seinen Lead schickt; eine Spanne, die Geschwister-Punkte verschluckt, ist
nicht dieser Absatz. Gebaut: `_own_block` — der Block endet an der ersten spaeteren Zeile, die am
Spaltenanfang einen neuen Block oeffnet (Listenzeichen oder Ueberschrift) oder an der Leerzeile;
eingerueckte Fortsetzungszeilen bleiben drin.

```
qualifizierende Aussagen mit dem neuen Leser (rung_read.py):  dev 1/35 · research 1/35 · office 0/27
ladder-paragraph-loses-the-effort-axis  (EINE Aenderung)      RED    1 failed
control-the-span-reader-misses-the-lost-axis (dieselbe Aenderung, alter Leser)  GREEN  1 passed
constitution-loses-the-paragraph-that-states-the-rule         RED    1 failed, 1 passed
constitution-grows-a-second-paragraph-that-states-the-rule    RED    1 failed, 1 passed
tools/test_review_procedure.py                                25 passed, 2 failed (Store-Naht, (c))
```

Der GRUENE Fall ist Absicht und die eigentliche Messung: mit dem alten Spannen-Leser bleibt genau
diese Mutation unbemerkt — der Zustand, den die Pruefrunde 4 gemeldet hat.

**Fuer die Naht (N18 nachgezogen):** was ein Kit schuldet, ist **eine** fettgefuehrte Aussage, die
**beide** Achsen **in sich selbst** traegt. G5-2s Fassung tut das nach dem Text, den sein Protokoll
zitiert; wer den Absatz umschreibt, darf die Effort-Achse nicht in einen Nachbarpunkt auslagern.
N18 versprach vorher mehr, als der Waechter hielt.

### N4-3 — die 67 warnings bei N8 standen unqualifiziert

Qualifiziert statt ersetzt: die Zeile sagt jetzt, mit welchem Kernel sie gemessen wurde, und zeigt
auf die eine Stelle mit der Zahl des laufenden Kernels (N20 (e)).

### N4-4 — Pruefer-Token in der (g)-Zeile

N19 hat jetzt zwei Zeilen: Umsetzer (A ~896 k, B siehe unten) und **Pruefer** (Runde 4 ~165 k aus
dessen eigenem Zaehler; Runden 1–3 nennen keine — das kann nur der Lead nachtragen, geschaetzt wird
nichts).

### Stempel, Patch, Uhr, Token dieser Nachbesserung

Geaendert wurden **zwei Testdateien** (`tools/test_migrate.py`, `tools/test_review_procedure.py`) —
**keine** Kit-Datei, also kein neuer Stempel: `bump_kit_version.py` **unchanged**, dev
`2026.09.06-9`, office `2026.09.06-8`, research `2026.09.06-10`. `ruff check .` und
`tools/validate.py`: siehe unten, beide gruen. Patch neu geschnitten, Pfad, Groesse und
`git apply --check` unten.

**Patch neu geschnitten** (`patch_make.py`, 20:07): `C:/Offline Repos/v2-testbed/_round-scratch/
TSK-0131/stream-stock.patch`, **258 531 Bytes, 37 Dateien, 0 CRLF-Zeilen**, keine VERSION-,
`project_memory/`-, `CLAUDE.md`-, `.claude/hooks`-, `settings.json`-, Kit-Hook-, `templates/`-,
`model_tiers`- oder `migrate.py`-Hunks; `git apply --check` gegen `git archive b7f282e` in einem
Wegwerf-Repository **rc 0**.

**Uhr (gelesen):** 19:53:02 bis 20:08. **Token:** gefuehrt an genau einer Stelle, N20 (g).
