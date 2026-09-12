# Prüfbericht TSK-0144 (PR-0012, Zielrunde) — Runde 2 — **PASS**

Prüfer: `harness-verifier` (Opus, high), 9 min, +38 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 21:14, Uhr gelesen). Rest (spannenweite Entschuldigung) als Loch aufgenommen; R6 Titel von BUG-0297 per Kernel korrigiert.

# Prüfbericht TSK-0144, Runde 2 (Nacharbeit), Prüfer Opus high M

Neue Momentaufnahme `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0144\verify2\` (21:04:38), Rig unverändert `...\verify-rig\` (verweigert außerhalb des eigenen Verzeichnisses, schreibt binär). Kein Volllauf wiederholt. Alle Mutationen zurückgenommen, gegen das Repo nachgewiesen (13 berührte Dateien, alle `identical`).

## Stempel

`bump_kit_version.py` → **unchanged ×3 (2026.09.12-6)**; die drei `content:`-Hashes gegen den echten Repo-Baum neu gerechnet und identisch: `b3d9091678a7…` / `31e315bbd01b…` / `82555431d508…`.

## B1 — behoben, und ein Rest, den die Nacharbeit neu aufgemacht hat

`tools/test_hooks.py:6973` (`_COMPUTED_FLAG_RX`), `:7018` (der Ausstieg), Docstring `:6996-7004`.

| Zustand | Ergebnis |
|---|---|
| ausgeliefert, ungepatcht | `1 failed in 3.91s`, Täter **nur** `.claude\hooks\gate_commit_evidence.py` |
| S4-Patch in der Kopie angewandt | **`1 passed in 3.90s`** — das ist die Hälfte, die letzte Runde gefehlt hat |
| Ausstieg gekappt (`if False and …`) | `1 failed`, Täter `.claude\hooks\gate_test_scope.py` — rot-zuerst hält |

**Neuer Rest (Ihr Auftrag „eine echte Auslassung neben einem `--%s`"), gemessen:** der Ausstieg gilt für die **ganze Spanne**, nicht für die berechnete Flagge. Drei Läufe, alle `1 passed`:

1. `--summary "full run"` aus `gate_test_scope.py`s Text entfernt, `--%s` bleibt → **grün**;
2. der **echte, ungepatchte** S4-Defekt in `gate_commit_evidence.py` plus eine plausible Zeile `--%s <the kind the verdict is>` in derselben Abhilfe → **grün**, der Schiedsrichter ist stumm;
3. dasselbe `--%s` gar nicht im Kommando, sondern in der **PowerShell-Hinweiszeile** daneben → **grün**. Die Spanne ist `evidence([^\`]*)` und läuft bis zum nächsten Backtick, die Entschuldigung leckt also über die Kommandogrenze.

Heute ohne Opfer (25 Spannen, genau eine berechnete, und die trägt gerendert alle Pflichtflaggen). Die Kette braucht eine künftige Textänderung, läuft also nicht innerhalb dieser Sitzung durch — **kein Blocker, aber ein zu benennendes Loch** (Mechanismus: *eine berechnete Flagge irgendwo vor dem nächsten Backtick entschuldigt jede echte Auslassung derselben Spanne*, nicht „die drei Stellen, die ich probiert habe"). Minimalfix, wenn er drankommt: nur so viele fehlende Namen entschuldigen, wie berechnete Token dastehen (`len(required - flags) <= Zahl der --%s`), oder die Spanne am Kommandoende abschneiden.

## B2 — behoben

`tools/test_repo_hygiene.py:2767`, jetzt `"%s:%d  %s()  %s" % one`. Vergessliche Fixture neu gepflanzt → die Fundliste **druckt**:

```
E   tools/test_hooks_v2.py:16415  verifier_plant_forgets_it()  [os.path.join(HOOKS, name)]
E   tools/test_hooks_v2.py:16424  verifier_plant_env_from_another_module()  [os.path.join(HOOKS, name)]
```
Kein TypeError mehr.

## B3 — behoben

Vierter Zustand `tools/test_review_procedure.py:1093-1112`: `SUPERSEDED` + `archive`, mit Nachweis, dass die Datei `active/` verlassen hat, und der Forderung, dass die Pflicht `PR-0002` **und** `SUPERSEDED` nennt (damit kann kein Restduft aus Zustand 3 sie erfüllen). Mutation `read_anywhere` → archivierte überspringen, je Kit einzeln:

* dev-team → `1 failed` (`tools\test_review_procedure.py:1106`)
* office-team → `AssertionError: office-team: an archived record is out of active/ …`
* research-team → `AssertionError: research-team: …`

Spiegel byte-identisch nach der Kommentaränderung: `_routine.py` 18966 B / `1333b554cc4a` in allen drei Kits, `test_hooks.py -k mirror` 2 passed. Der Kommentar (`_routine.py:255-261`) sagt jetzt ausdrücklich, dass Archivieren ein **eigener** Schritt ist (`kernel.state.archive`, das `archive`-Kommando) — der Punkt, den ich letzte Runde als ungenau gemeldet hatte, ist mit erledigt.

## R2 / R4 / R5

* **R2 behoben** mit einem eigenen Knoten `tools/test_hooks_v2.py::test_a_row_with_too_FEW_columns_stops_the_write_as_well`: grün; kurzer Arm (`None in row.values()`) gekappt → **`1 failed` (`:9180`)**. Der alte Nachbar bleibt unter demselben Schnitt grün — das steht im Docstring des neuen Knotens samt Grund (der Append-Pfad hat einen zweiten Leser, deshalb ist `--validate` das Subjekt). Ich hatte in Runde 1 erwartet, der alte Knoten müsse rot werden; das war falsch, die Messung des Umsetzers ist die richtige.
* **R4 behoben**: die Zahl steht nicht mehr im Docstring (`tools/test_role_contracts.py:2258-2260`), nur der Zeiger. *Kleinigkeit*: „the number lives in `tools/lead_package_sizes.json` and nowhere else" — ein Grep findet sie auch in `docs/reviews/phase0-disposition.md:2086`, dort als datierte Verlaufszeile. Entweder „nowhere else that is read" oder die drei Worte streichen.
* **R5 behoben**: `lead-lines.md:134-138` nennt jetzt genau zwei (`BUG-0237`, `BUG-0286`), zählt die sieben übrigen Fragezeilen auf, die **nicht** in den 21 stehen, und sagt, dass `BUG-0203`/`BUG-0212` keine Fragezeilen sind — mit dem Hinweis, dass eine frühere Fassung das behauptete.

## Wiederholte Abnahmemessungen

* Zehn Batch-Zeilen gegen den aktuellen Store, read-only über `approvals.batch_walk_blockers`: **10/10 Zeilen `refused 0`, 68 Ids, 68 distinct, keine Doppelung**; Rollup **89** Zeilen, `unresolved` überall leer, **68** in den Zeilen, **0** Zeilen-Ids außerhalb, **21** ohne Zeile — Id-für-Id dieselben wie im Dokument.
* `ruff check tools team-kits` → All checks passed; `tools/validate.py` → all structural checks passed.
* **index = store**: auf einer frischen Store-Momentaufnahme regeneriert, einziger Unterschied `generated_at`. (Der Repo-Index trug beim Vergleich zwei Items mehr als meine Kopie — `BUG-0299`/H215 und `BUG-0300`/H216, um 21:05 aufgenommen, also nach meinem Snapshot. Das sind genau meine Reste R1 und R3 als Löcher; keine neue `EVD` dazu, der Volllauf blieb unwiederholt.)

## Offen geblieben (unverändert aus Runde 1)

* **R6**: `docs/POST_V2_WISHLIST.md:2516`, Zeile H213, trägt weiter den **Titel** „…und nichts im Baum wird währenddessen rot". Das `limits`-Feld von `BUG-0297` ist korrigiert („seit der Zielrunde TSK-0144 wird ein Test in tools/ rot"), der Titel — aus dem die Indexzeile gebaut wird — nicht. Ein Titelwechsel beim Rundenabschluss, Sache des Leads.
* **R7**: die drei `oversize`-Knoten in `tools/test_migrate.py` sind in einer `.git`-losen Kopie nicht fahrbar (Setup bricht ab) — Rig-Hinweis, kein Defekt.

**Nicht gemessen:** der Volllauf (DEC-0050), die vollständige Gate-Suite, die fünf nicht mutierten Erstlauf-Roten, C's `limits-update-lines.md`, Spiegel jenseits der zwei Mirror-Knoten und `_routine.py`.

---

## URTEIL: **PASS**

B1, B2, B3, R2, R4, R5 sind geschlossen und jeweils mit einem Test belegt, der ohne den Fix rot wird — von mir selbst gefahren, nicht nachgelesen. Stempel, Hashes, Zeilen, ruff, validate und Index stimmen.

**Als benannter Rest in die Löcherliste, bevor die Runde zugeht** (gemessen und daher schriftpflichtig): die **spannenweite Entschuldigung** in `tools/test_hooks.py:7018` — eine berechnete Flagge irgendwo vor dem nächsten Backtick macht den S4-Schiedsrichter für jede echte Auslassung derselben Spanne stumm, gemessen am ungepatchten Original-Defekt (`1 passed`). Kein Blocker, weil die Kette eine künftige Textänderung braucht; aber es ist dieselbe Stille, gegen die H108 überhaupt erst von Hand gefunden wurde, und sie gehört als Item neben H215/H216, nicht in diesen Bericht allein.