# Prüfbericht TSK-0144 (PR-0012, Zielrunde) — Runde 1 — **FAIL (B1 B2 B3, je Einzeiler in tools/)**

Prüfer: `harness-verifier` (Opus, high), 31 min, 217 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 20:41, Uhr gelesen). Nacharbeit an M; R5/R6 Lead.

## Prüfbericht TSK-0144 (Merge-Runde PR-0012 „Bug-Null"), Prüfer Opus high M

Arbeitskopie: `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0144\verify\` (robocopy, ohne `.git`/Caches), Rig: `...\TSK-0144\verify-rig\` (verweigert außerhalb des eigenen Verzeichnisses, schreibt binär). Repo selbst nur gelesen. Kein Volllauf wiederholt (DEC-0050). Kein Dokument ganz gelesen außer `lead-lines.md` (140 Z.) und `TSK-0144.yaml`; vom Protokoll die benannten Abschnitte.

---

## BEFUNDE

### B1 — blockierend: Der „S4-Schiedsrichter" ist keiner. Nach dem Nutzer-Patch bleibt der Knoten rot — an einer zweiten, für jede Rolle verbotenen Datei, deren Text KORREKT ist

`tools/test_hooks.py:6982-6988` (Docstring-Behauptung), `:6902` (die verbreiterte Korpus-Zeile), `:7000-7006` (der Leser) — gegen `.claude/hooks/gate_test_scope.py:709-719`.

Der Docstring sagt: *„THIS NODE IS THE ARBITER OF SEAM S4 … Until it is applied this node fails"*. Gemessen, in meiner Kopie:

1. ungepatcht: `1 failed in 121.33s`, Täter `.claude\hooks\gate_commit_evidence.py` — wie behauptet;
2. S4-Patch angewandt (exakt der Text aus `staging/TSK-0141/s4-gate-commit-evidence-patch.md`, `ast.parse` grün): **`1 failed in 3.46s`**, Täter jetzt

```
E   AssertionError: .claude\hooks\gate_test_scope.py spells an `evidence` call ` \
E                 --kind test --result pass --related <ITEM-ID> \
E                 --summary "full run" --artifact-ref <path> \
E                 --%s full --%s "<the line above, verbatim>"` that omits --run-command, --run-scope.
```
3. Korpus-Sonde über `_texts_that_name_the_evidence_vocabulary()`: `seen calls: 25, offending: 1` — genau diese eine Stelle.
4. Der **gedruckte** Text ist richtig. Ich habe den Refusal-Ausdruck des Moduls selbst ausgewertet (AST → `compile`/`eval` mit den Modulkonstanten): `--run-scope full --run-command "<the line above, verbatim>"`.

Also: der Leser liest den **Quelltext** eines Refusal-Strings statt der Nachricht, die die Rolle bekommt — genau die Hausregel „eine Prüfung muss den Teil lesen, der läuft", angewandt auf den Korpus, den diese Runde erweitert hat. Folge: **nach** dem Nutzer-Patch ist `pytest tools/` dauerhaft rot, und niemand hier darf es reparieren (`.claude/hooks/gate_*.py` ist `forbidden_scope`). Zusätzlich ist der Satz im S4-Patchdokument *„`gate_test_scope.py:709-712` already carries the pair and needs nothing"* für genau diesen Leser falsch.

Minimalfix: im Leser eine berechnete Flagge als „nicht ausgeschrieben" behandeln (Span mit `--%s`/`--{}`-Form überspringen, wie `if not flags: continue`) **oder** den gerenderten Text beurteilen; und den Docstring-Satz korrigieren, der die Grünfärbung nach dem Patch verspricht.

### B2 — blockierend: Der H196-Sweep kann seinen eigenen Befund nicht drucken (TypeError statt Fundliste)

`tools/test_repo_hygiene.py:2764-2767`:

```python
% (len(forgetful), "\n  ".join("%s:%d  %s" % one for one in forgetful)))
```
`forgetful` trägt 4-Tupel (`where, lineno, owner, argv`, gebaut `:2734-2735`), das Format hat drei Platzhalter. Gemessen, nachdem ich eine vergessliche Fixture in eine echte Suite-Datei gepflanzt habe:

```
E   TypeError: not all arguments converted during string formatting
tools\test_repo_hygiene.py:2767: AssertionError → FAILED
```
Der Schutz greift (rot bleibt rot), aber die Meldung ist ein Absturz. Damit ist die Rot-zuerst-Zeile des Protokolls (*„RED on this tree … 14, then 15 findings with file, line, function and argv"*) mit dem ausgelieferten Knoten **nicht reproduzierbar** — sie kann nur vor der letzten Änderung des Formats entstanden sein. Hausregel 5: der rote Test des Fixes ist eine Behauptung, und diese hier misst sich anders als geschrieben.

Minimalfix: `"%s:%d  %s  %s" % one`.

### B3 — blockierend für die Zeile H158: der Archiv-Arm ist tragend und von keinem Test gedeckt

`team-kits/{dev,office,research}-team/hooks/_routine.py:255-258`, Kommentar: *„READ ANYWHERE, not just `active/` … ein Leser, der nur `active/` kennt, verfehlt genau die Datensätze, für die diese Funktion existiert."*

* Mutation in **allen drei** Kits (`read_anywhere` → archivierte überspringen): `tools/test_review_procedure.py -k delivery_since_the_last_run` → **`1 passed, 28 deselected in 10.02s`**. Der Knoten schweigt.
* Grund, gemessen: die Fixture läuft ein **PR** nach `DELIVERED` — kein Terminal, also bleibt es in `active/`; der Archiv-Arm wird nie berührt.
* Dass der Arm wirklich trägt, separat gemessen (Mini-Store, `archive/tsk/2026/TSK-0001.yaml`, `VALIDATED`): ausgeliefert → `[('TSK-0001','VALIDATED')]`, mutiert → `[]`.

Nebenbei ist der Kommentarsatz „a task is ARCHIVED the moment it reaches its terminal status" ungenau: Archivieren ist ein eigenes Kommando (`kernel/state.py:1641`, `cli.py:1995`), keine Automatik der Transition.

Minimalfix: vierter Zustand im benannten Knoten — den gelieferten Datensatz archivieren (oder einen `TSK` nach `VALIDATED` fahren und archivieren) und prüfen, dass die Pflicht ihn weiter NENNT.

---

## RESTE (gemessen, nicht blockierend — gehören benannt in die Löcherliste)

* **R1 — H196-Leser sieht die häufigste Schreibweise nicht.** `tools/test_repo_hygiene.py:2611` (`_starts_a_hook`) folgt einem `argv`, das ein Name hält, aber nicht dem **Programmwort**. Gepflanzt: `program = os.path.join(tmp,"gate_write_scope.py"); subprocess.run([sys.executable,"-B",str(program)], env=dict(os.environ))` → **stumm** (2 von 3 Pflanzungen genannt). Live-Sprechstellen dieser Form: 4 (`tools/test_hooks_v2.py:13506`, `:14569`, `tools/test_repo_hygiene.py:2588`, `.claude/hooks/test_gates.py:344`). **Heute kein Opfer**: mit einem zusätzlichen Element-Hop bleibt der Sweep bei `still forgetful with the hop: 0`. Fix: denselben `bound`-Hop auch auf das Programmwort.
* **R2 — `is_malformed`, ein Arm ungedeckt.** `team-kits/office-team/templates/repo/scripts/ledger_add.py:254`. Zu-lang-Arm gekappt → `1 failed` (Original-TypeError). Zu-kurz-Arm (`None in row.values()`) gekappt → **`1 passed`**, obwohl der Docstring beide Formen als „one question" nennt.
* **R3 — die gemessene Unterscheidung im Stopper-Leser hat keinen roten Test.** `tools/test_hooks.py:9131-9137` begründet „CANNOT RETURN" statt „exits somewhere" mit 45 vs. 3 Namen. Mit einer originalgetreuen Erst-Fassung mutiert (hier: 46 vs. 3 Namen in `.claude/hooks`, 55 vs. 15 im dev-Bündel) bleibt `test_the_refusal_reader_finds_a_stopper_this_repos_own_gates_spell` **grün** — das synthetische Bündel enthält keine Funktion, die in einem Zweig verweigert und im anderen zurückkehrt. (Der Arm-2-Schnitt geht korrekt rot: `AssertionError: []`.)
* **R4 — Zahl an zweiter Stelle.** `tools/test_role_contracts.py:2259` schreibt „62894 bytes" in einen Docstring; ihr Ort ist `tools/lead_package_sizes.json`. Inhaltlich stimmt sie heute (gemessen: research `size 62894 / ceiling 62894`), sie altert aber beim nächsten `record_lead_package_sizes.py --write`. Fix: Zeiger statt Zahl.
* **R5 — Falschzuordnung in der Übergabe.** `project_memory/staging/TSK-0144/lead-lines.md:123`: *„Four of them are the QUESTION rows of section 3 (`BUG-0237`, `BUG-0286`, `BUG-0203`, `BUG-0212`)"*. Abschnitt 3 führt neun Ids (0237, 0252, 0253, 0286, 0260, 0248, 0164, 0056, 0221); `BUG-0203`/`BUG-0212` stehen dort nicht und im ganzen Dokument nur in der 21er-Liste selbst. Der Lead sucht sonst nach zwei Fragetexten, die es nicht gibt.
* **R6 — Löcherliste widerspricht dem gebauten Stand.** `docs/POST_V2_WISHLIST.md`, Zeile H213 (`BUG-0297`, angelegt 14:03): *„nichts im Baum wird währenddessen rot"* — seit Naht (c) falsch. Lead-Datei, nicht die des Umsetzers.
* **R7 — Rig-Hinweis.** `tools/test_migrate.py` (drei `oversize`-Knoten) bricht in einer `.git`-losen Kopie im Setup ab (`git could not read this repository's history`) — Rot-zuerst für diese Klasse ist in der vorgeschriebenen Kopie nicht fahrbar.

---

## NEGATIVBEFUNDE

**Gemessen und in Ordnung**

* Stempel: `bump_kit_version.py` in der Kopie → **unchanged ×3 (2026.09.12-5)**; die drei `content:`-Hashes gegen den **echten Repo-Baum** neu gerechnet (`kernel.hashing.kit_hash`) — identisch (`a51ebdb2…`, `a643b99c…`, `db991ac5…`).
* EVD-0413: `kind: test`, `run_scope: full`, `related: [PR-0012]`, `run_command` mit `DELIVERY_RUN=TSK-0144`; Zählwerk nicht nachgefahren (DEC-0050), Arithmetik konsistent (9+5068 → 1+5077 = ein Test mehr, deckt sich mit dem neuen `test_an_item_file_too_big_to_open_is_reported_and_is_not_opened`).
* BUG-0265/H183: Fix gekappt → `assert (0, 0) == (1, 4)` — exakt die Protokollzeile. (Wichtig: nach einer Kernel-Mutation muss neu gestempelt werden, sonst ist das Rot das des Installers, nicht das des Mechanismus — erst so gemessen.)
* H55: die Aussage wird aus **echtem stdout** gelesen — Satz in einen Kommentar verschoben (Datei trägt die Worte weiter) → `1 failed`.
* `test_every_approval_refusal_the_hook_can_surface_speaks_to_the_user` ist **vorbestehend**: Knoten unverändert seit 10a5127 (Diff), mit der Basis-`approvals.py` → `1 failed`, sechs Treffer, alle in `consumed_request`.
* Größenschranke `state._walk_stored_files` an **beiden** Enden rot: Schranke entfernt → `tools/test_migrate.py` rot (`'big.yaml' not in {...}`); `oversized_stored_files` stummgeschaltet → `tools/test_report.py::test_an_item_file_too_big_to_open_is_reported_and_is_not_opened` rot.
* `known_holes.json` **Delta null**: 1044 B / `f45e24885e7c` vor und nach `gen_known_holes.py`, Digest 495 B / `f5bbde32d746`; 3+1+4 markierte Tests.
* `ruff check tools team-kits` → All checks passed; `tools/validate.py` → all structural checks passed; `generate-index` = Store (einziger Unterschied `generated_at`); Spiegel: `test_hooks.py -k mirror` 2 passed, `_routine.py` in allen drei Kits 18607 B / `ff5c4e7f621c`.
* Gate-Suite: genau **ein** Roter, `test_every_test_a_hole_names_is_one_that_exists`, und nur wegen H138; die H158-Hälfte ist weg. Unerreichbar für den Kernel, wörtlich reproduziert: `no active item BUG-0221 … a finished item lives in the archive rather than among the active ones`.
* `lead-lines.md` Abschnitt 1 und 5 vollständig nachgebaut (eigenes Rig, read-only, `batch_walk_blockers` + `stock_rollup`): **10 Zeilen, 68 Ids, 68 distinct, 0 Doppelte, je `refused 0`**; Rollup **89** Zeilen, `unresolved` überall leer, **68** in den Zeilen, **0** Zeilen-Ids außerhalb des Rollups, **21** ohne Zeile — Id-für-Id identisch mit der Liste im Dokument. Alle 21 stehen auf `TRIAGED`/`OPEN` und tragen eine `limits`-Prosa (aber: 84 der 89 tun das, `limits` ist also kein Unterscheidungsmerkmal — R5 bleibt nur die Fehlzuordnung).
* Laufzeit des neuen Anlass-Laufs (Sicherheitsfrage, SessionStart): auf diesem Store (2151 Dateien) **0,04 s / 0,34 s / 0,97 s / 1,07 s** für „seit 0 / 1 / 30 / 3650 Tagen" — kein Budgetproblem.
* Naht (b) erledigt: `tools/test_repo_hygiene.py:1335-1336` nennt alle drei Antworten.

**Nicht gemessen (bewusst)**

Der Volllauf selbst (DEC-0050 — ich rechne nach, ich wiederhole nicht); die vollständige Gate-Suite (nur der eine Knoten); fünf der neun Erstlauf-Roten (vier Scaffold-Preset-Knoten, `only_some_tool_caches`) nicht mutiert; die Kit-Seite der Hook-Fristen (`team-kits/*/settings/settings.json` ist `forbidden_scope`); C's `limits-update-lines.md`; die Prosa in `docs/holes/*.md`; die Spiegel jenseits der zwei Mirror-Knoten und `_routine.py`; Arm 3 von Naht (c) (`_evidence_call_rx`) — vom Umsetzer selbst als ungedeckt ausgewiesen, das habe ich übernommen und nicht nachgemessen.

---

## URTEIL: **FAIL**

**Blockierend für die Runde:** B1 und B2. B1 weil die Runde einen Knoten ausliefert, der in diesem Repo **nie** grün werden kann und dessen Docstring das Gegenteil verspricht — damit wäre „der Volllauf ist grün" ab sofort für jede künftige Runde unerreichbar, und der Nutzer würde nach seinem Shell-Patch dieselbe Rotfärbung sehen wie davor. B2 weil der rot-zuerst-Nachweis der reservierten Zeile H196 mit dem ausgelieferten Knoten nicht erzeugbar ist. Beide sind Einzeiler-Reparaturen in Dateien, die dem Umsetzer offenstehen (`tools/**`).

**Blockierend für die Zeile, nicht für das Paket:** B3 (H158) — ein Zustand mehr im benannten Knoten.

**Als benannte Reste in die Löcherliste:** R1 (Mechanismus: ein Programmwort, das erst ein lokaler Name auflöst, ist dem Startleser unsichtbar — nicht „die zwei Schreibweisen, die ich probiert habe"), R2, R3, R4, R7; R5 und R6 sind Übergabe-Korrekturen für den Lead.

**Eigene Fehlgriffe:** Meine erste H158-Mutation lief gegen einen kaputten Fixpunkt und war als Messung wertlos (rot aus dem falschen Grund) — erst die zweite, originalgetreue Fassung war die Aussage. Und mein erster BUG-0265-Rotlauf war ein Stempel-Rot des Installers, kein Mechanismus-Rot; die berichtete Zeile ist die nach dem Neustempeln.