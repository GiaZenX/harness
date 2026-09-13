# Prüfbericht TSK-0147 (PR-0012, Order 4, Strom B Kits) — Runde 2 — **PASS (zwei benannte Über-Verweigerungen → Zielrunde; docs-Seite → Zielrunde)**

Prüfer: `harness-verifier` (Opus, high), 18 min, +54 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 01:46, Uhr gelesen).

# Prüfbericht Runde 2 — Strom B (die drei Kits), TSK-0147 / PR-0012

**Urteil: PASS** für das Paket von Strom B. Zwei benannte Über-Verweigerungen gehören in die Löcherliste, und **eine fremde Zeile blockiert weiterhin die RUNDE** (die Docking-Point-Seite unter `docs/`, nicht B's Bereich).

Neuer Schnappschuss (01:3x), beide Piloten aus dem echten `scaffold_team.sh` neu gebaut, alle Zahlen unten sind eigene Messungen mit echten Hook-Prozessen.

---

## F1 — BUG-0298/H214: geschlossen

Alle acht Zeilen, beide Piloten, verweigert von `gate_write_scope` („this line WRITES run.sh and RUNS it in the same call"):
`cat…>run.sh; bash run.sh` · `. run.sh` · `source run.sh` · `. ./run.sh` · `tee run.sh <<EOF; bash run.sh` · `tee…; sh run.sh` · `echo x | tee run.sh && sh run.sh` · `printf > run.sh && bash run.sh` — **16 von 16 rc 2**.
Alltag unberührt, **14 von 14 rc 0**: `cat <<'EOF' > notes.md`, `bash tools/ci.sh`, `cp a.sh b.sh`, `tee log.txt < x`, `git status --short`, `python -m pytest`, `cp a.txt b.txt ; cat b.txt` — je beide Piloten. Zusätzlich ohne Falschalarm: `tar -xzf pkg.tgz ; bash pkg/install.sh`, `make build && bash scripts/deploy.sh`, `npm run build && node dist/main.js`, `echo hi > out.txt ; bash tools/ci.sh`, `git clone … && bash repo/setup.sh`, `. venv/bin/activate && python -m pytest -q`, `python -m venv venv && . venv/bin/activate`, `source ~/.bashrc`.

Zwei neue Schreibweisen, wie erbeten — **beide rc 2, beide Piloten**:
- `install -m755 src.sh run.sh ; ./run.sh` und `cp x.sh run.sh ; ./run.sh` → **Klasse „schreibfähige Stufe nennt die Datei als eigenen Operanden"** — dieselbe Klasse wie `tee`, durch `_stage_is_read_only` fail-closed gedeckt, ohne Liste. Ebenso `mv x.sh run.sh && bash run.sh`, `printf > run.sh ; env bash run.sh`, `printf > run.sh ; exec bash run.sh`.
- `printf 'x' > r.py ; python r.py` → **rc 0 = Interpreter-Klasse**, im Docstring als H11-Rest benannt (`gate_write_scope.py`, „WHAT IS LEFT OPEN AND NAMED RATHER THAN CLAIMED AWAY"). Korrekt benannt, nicht wegbehauptet.

Stolperdraht: `_operand_words` (`gate_write_scope.py:1527`) auf `return []` mutiert → `tools/test_hooks.py -k writes_a_script_and_runs_it` **3 passed → 3 failed**, nach Rücknahme wieder 3 passed (12,0 s).

## F2 — Falschalarm weg, Regel hält

Beide Piloten, Sitzungsinstanz **und** Kind, je **rc 0**: `curl --fail`, `grep --fixed-strings`, `git log --format=%H -n 3`, `python -m pytest --failed-first`, `docker build --file Dockerfile .`, `rsync --files-from=list.txt`.
Weiterhin **rc 2** auf einer Kernel-Einstiegszeile: `--fail-class mechanical`, Präfix `--f`, und die `python -m kernel.cli`-Schreibweise — von der Sitzungsinstanz („the session instance may not classify a failed run") wie vom ungebundenen Kind („no lease binds the agent").
Zeiten (Minimum aus drei Läufen, `gate_dispatch` allein): ohne lange Option **0,12 s**, mit beliebiger langer Option **0,12–0,16 s** (vorher 0,24–0,30 s), `python scripts/harness.py show TSK-1` **0,12–0,13 s**. Nur die tatsächlich geprüfte `evidence`-Zeile kostet **0,28–0,38 s** — B's „0,18–0,20 s" ist für die Evidence-Zeile zu optimistisch, die Richtung stimmt und die Alltagskosten sind niedriger als behauptet.

## F3 — geschlossen; die Grenze der Verweigerung ist zu nennen

`a="--"; b="fail-class"; python scripts/harness.py evidence … "$a$b" mechanical` → **rc 2** in beiden Piloten („this line carries a word the shell builds, so whether it classifies cannot be read"). Backtick-Form ebenfalls rc 2 (dort vom F1-Leser).

**Antwort auf die gestellte Frage — Über-Verweigerung oder Befund:** die Bindung ist weiter als der Mechanismus, und das ist zu schreiben, nicht zu schließen. Gemessen, beide Piloten, jeweils rc 2:
```
python scripts/harness.py evidence … --summary "$MSG" --artifact-ref staging/x/run.log
python scripts/harness.py evidence … --related "$ID"
python scripts/harness.py evidence … --run-command "$(cat cmd.txt)"
```
Eine `evidence`-Zeile ohne Expansion ist rc 0, eine NICHT-`evidence`-Harness-Zeile mit `$T` ist rc 0 — die Bindung an `evidence` hält also. Aber: `--run-command "$(…)"` ist genau die Zeile, die die QA-Rolle täglich schreibt. Bewertung: **akzeptable fail-closed-Richtung, aber ein zu benennender Rest** — ein **quotiertes** Wort in Wertposition kann keine Option einführen (nur ein unquotiertes wortteilt), also ließe sich die Regel ohne Verlust auf unquotierte Expansionen verengen. Bis dahin: in die Löcherliste als Über-Verweigerung mit dieser Messung, und die drei Rollentexte sollten den Fall nennen, damit die QA-Rolle nicht in eine Wand läuft, die ihr niemand angekündigt hat.

## F4 — genau eine Datei rot
`tools/test_hooks.py -k evidence_command`: **1 failed**, und der einzige Fund ist `.claude\hooks\gate_commit_evidence.py` (der S4-Patch des Nutzers, H213). Die beiden Kit-Rollentexte stehen nicht mehr in der Liste.

## F5 — ein Mischbeleg ist ein Beleg
Ein unbezahlter Mischbeleg, echter Skriptlauf:
```
[euer_report] … written (3 paid entries, 1 open items)
| L2026-0004 L2026-0005 RE-2026-0004 | Kaeufer GmbH | 2026-09-01 | 333.00 EUR |
```
Eine Zeile, Brutto summiert (119,00 + 214,00). Buchung selbst unverändert: Einzelsatz eine Zeile; Misch zwei Zeilen unter einer Rechnungsnummer, `ledger_add` rc 0 ×2, `--validate` rc 0, Doppelbuchung derselben Zeilen rc 1.

## F6 — der Stolperdraht existiert und kann rot werden
`tools/test_hooks.py::test_every_shipped_hook_of_this_kit_reaches_the_deadline_that_arms_it`: grün über die drei Kits; mit `start_the_deadline()` aus `_compat.load()` entfernt **3 failed**, nach Rücknahme grün. Der Test leitet die Hook-Liste aus dem Verzeichnis ab (keine Aufzählung).
Die beiden Office-Recorder selbst gemessen, Eintrag ohne Fenster:
```
record_booking_reading.py  rc=0  Satz „…no entry that names it states a `timeout`" vorhanden
record_filing_reading.py   rc=0  dito
```
Also bewaffnet und bewusst schluckend — genau, was der Docstring sagt. Was dort NICHT gemessen ist (und auch nicht behauptet wird): dass der Watchdog-`os._exit(2)` in diesen beiden wirklich durchschlägt.

## Neuer kleiner Befund (Runde 2): eine Verweigerung, die etwas Falsches behauptet
`team-kits/*/hooks/gate_write_scope.py` (F1-Regel, `_operand_words` + `_name_readings` über eine **unquotierte** Kommandoersetzung). Gemessen, beide Piloten, jede Rolle:
```
bash $(which ci.sh)     -> rc 2  „[team-kit gate_write_scope] this line WRITES ci.sh and RUNS it in the same call…"
bash "$(which ci.sh)"   -> rc 0
bash $(cat name.txt)    -> rc 0   (cat gilt als nur lesend)
sh $(mktemp)            -> rc 0
```
Die Zeile schreibt `ci.sh` nicht — die inneren Wörter der Ersetzung werden als Operanden einer schreibfähigen Stufe gelesen. **Schwere: gering** (Über-Verweigerung, kein Durchlass), aber der Satz behauptet etwas, das nicht auf der Zeile steht (Hausregel 3 gilt auch für Verweigerungstexte). **Minimalfix:** ein Wort, das erst eine Ersetzung herstellt, ist unplatzierbar und nicht „diese Zeile schreibt X" — entweder mit dem vorhandenen Unplatzierbar-Satz verweigern oder die Stufen innerhalb einer Ersetzung nicht in die WRITTEN-Menge nehmen.

## Weiteres, gemessen
- **EVD-Benennung:** EVD-0435 (`…writes_a_script_and_runs_it…`), EVD-0436 (`…only_looks_like_a_classification_is_left_alone`), EVD-0438 (`…reaches_the_deadline_that_arms_it`), EVD-0439 (`…is_one_beleg_everywhere_the_report_counts_them`) — alle `result: pass`, alle Knoten existieren und laufen bei mir grün (5 passed, 7,8 s; darunter auch `…refused_from_every_writer_but_the_verifying_one`, womit die **Annahme-Richtung des gebundenen QA-Kindes** jetzt von mir selbst gemessen ist — sie war in Runde 1 mein „nicht gemessen").
- **Batch-Zeile:** eigener Trockenlauf in einer `git init`-Kopie mit `project_memory`, `team-kits`, `tools`, `.claude` → **rc 0**, die Frage listet alle sechs Ids mit ihren EVDs, **0 verweigert**. (Der erste Versuch ohne `tools/` wurde mit „resolves to no test in this checkout" verweigert — der Kernel prüft den Knoten wirklich gegen den Checkout.)
- **Spiegel:** abweichend genau `session_status.py`, `format_on_write.py`, `document_trays.txt`, `ENFORCEMENT.md` = die vier `KIT_SPECIFIC_HOOKS`-Namen.
- **Fenster:** 92/92 Einträge mit `timeout` (120 ×90, 1800 ×2).
- **Decke, Pins, Zeiger, Fenster-Ableitung:** `test_context_budget.py test_role_contracts.py` + `-k "context/role/constitution/pointer…/registration_names_a_window/default_window"` → **114 passed, 1 skipped, 147 s**.
- **ruff** über `team-kits/ tools/`: All checks passed.

## Nicht gemessen
- Volle Suite, Stempel (`bump_kit_version.py`), die drei stempelabhängigen Roten.
- Strom A (Kernel) und dessen Hälften von BUG-0260/BUG-0302; B's transienter Fremd-Roter (`…break_alike`, 22 failed → 187 passed) — nicht nachgestellt.
- Der Codex-Pfad der Deadline-Verweigerung (`stop(msg, "PreToolUse")` auch für Post/SubagentStop-Hooks) — steht weiter als Beobachtung, nicht als Messung.
- Ob der Watchdog in den beiden Office-Recordern wirklich durchschlägt (nur die Bewaffnung gemessen).

## Was noch die RUNDE blockiert (nicht B)
`docs/office/invoice-app-docking-point.md:60-61`, `:141`, `:240` — unverändert: „an invoice with two VAT rates is … refused for booking with the sentence »book by hand«", „two VAT rates" als Ablehnungsgrund in der rc-Tabelle, und §7 („business books such a document by hand"). Der ausgelieferte Code akzeptiert solche Belege und liefert `booking.rows` statt `booking.ledger_add`. Eine App, die dieser Seite folgt, liest einen Schlüssel, den es bei Mischbelegen nicht mehr gibt. B hat das korrekt als Seam 3 übergeben (`docs/**` ist verbotener Bereich); vor dem Merge muss die Seite nach.

## Eigene Fehlmessungen dieser Runde
- Mein erster Batch-Trockenlauf war ohne `tools/` aufgesetzt und meldete „6 of 6 cannot be closed" — das war mein Kopierfehler, nicht B's Zeile; mit vollständiger Kopie rc 0.
- In Runde 1 hatte ich für BUG-0300 zuerst die falsche Stelle mutiert (den `Return`-Vorfilter statt `_cannot_return`) und daraus „Mutation bleibt grün" gelesen; die richtige Mutation ist rot.