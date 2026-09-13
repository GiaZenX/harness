# Prüfbericht TSK-0147 (PR-0012, Order 4, Strom B Kits) — Runde 1 — **FAIL (F1 F2 F4 blockierend; F3 Rest; F5-F7 klein; F8 Zielrunde)**

Prüfer: `harness-verifier` (Opus, high), 28 min, 220 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 00:57, Uhr gelesen).

# Prüfbericht — Strom B (die drei Kits), TSK-0147 / PR-0012, Runde 4

**Urteil: FAIL.** Vier blockierende Befunde, drei benannte Reste. Gemessen mit echten Hook-Prozessen gegen zwei selbst gebaute Piloten (dev, office) aus einem Schnappschuss des Baums, Rig unter `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0147\rig\rig.py` (verweigert Lauf außerhalb des eigenen Verzeichnisses, schreibt sein Protokoll binär), Piloten über den echten `scaffold_team.sh` aus einem Fake-HOME (Kit-Kopien dort selbst gestempelt, damit der Scaffold nicht zurückrollt).

---

## Blockierende Befunde

### F1 — BUG-0298/H214 ist NICHT geschlossen: drei Schreibweisen desselben Mechanismus laufen durch
`team-kits/{dev,office,research}-team/hooks/gate_write_scope.py:1512` (`_refuse_a_script_this_line_writes_and_runs`), zusammen mit `team-kits/*/hooks/_compat.py:781` (`runs_the_file_it_is_handed`, Vokabular `_SHELL_NAMES`, `_compat.py:712`).

Die Menge „geschrieben" kommt ausschließlich aus `_redirect_targets` (`gate_write_scope.py:1216`) — also nur aus Shell-**Umleitungen**. Die Menge „ausgeführt" kommt nur aus `_SHELL_NAMES` = `bash|sh|zsh|dash|pwsh|powershell|cmd`. Damit fehlen (a) jedes Werkzeug, das seine Datei als **Operand** schreibt (`tee`), und (b) die Shell-**Builtins**, die eine Datei ausführen (`source`, `.`).

Gemessene Zeilen (beide Piloten, alle registrierten PreToolUse-Bash-Einträge, Körper `rm -rf project_memory` + `git push --force origin main`):

```
cat <<'EOF' > run.sh … EOF  bash run.sh   -> REFUSED (gate_write_scope)   [Referenz, der Fix]
cat <<'EOF' > run.sh … EOF  . run.sh      -> *** ALLOWED rc0 ***
cat <<'EOF' > run.sh … EOF  source run.sh -> *** ALLOWED rc0 ***
cat <<'EOF' > run.sh … EOF  . ./run.sh    -> *** ALLOWED rc0 ***
tee run.sh <<'EOF' … EOF    bash run.sh   -> *** ALLOWED rc0 ***
tee run.sh <<'EOF' … EOF ;  sh run.sh     -> *** ALLOWED rc0 ***
echo x | tee run.sh && sh run.sh          -> *** ALLOWED rc0 ***
```

Echte Shell als Schiedsrichter (`m_realshell.py`, Sandbox): beide Formen schreiben **und** führen aus — `proof_dot.txt = b'sourced\n'`, `proof_tee.txt = b'teed\n'`, rc 0. Die Angriffskette von H214 läuft also unverändert innerhalb einer Sitzung.

Dazu Hausregel 3: der Docstring des Fixes behauptet ausdrücklich Deckung, die der Code nicht baut — `gate_write_scope.py:1521`: „How the bytes get into the file does not matter (`cat <<EOF >`, `printf >`, **`tee`**)". Gemessen: `tee` ist nicht gedeckt. Der benannte Test `tools/test_hooks.py:19890` misst nur `>`+`bash`.

**Schwere: blockierend** (Kette läuft in einer Sitzung durch; DEC-0102 (2): der Mechanismus war zu benennen, nicht zwei Schreibweisen).
**Minimalfix:** `written` aus *jedem* Wort bilden, das eine schreibfähige Stufe als eigenen Dateioperanden nennt (die `sinks`-Lesung, die das Gate für `tee` an anderer Stelle bereits hat — `echo … | tee project_memory/…` wird korrekt verweigert), und `runs_the_file_it_is_handed` als Eigenschaft „das Programm führt seinen Operanden aus" fassen, inkl. `source`/`.`; den Rest (`python`, `node`) wie gehabt als H11 benennen.

### F2 — DEC-0107-Hookhälfte: `curl --fail` wird verweigert (Falschalarm auf jedem Shell-Aufruf)
`team-kits/*/hooks/gate_dispatch.py:219` (`_names_the_classification`). Der Docstring fragt „Does this shell line hand **the kernel** a fail classification?" — der Code fragt das nie: er prüft nur, ob irgendein `--wort` der Zeile ein **Präfix** von `--fail-class` ist. `--fail` ist eines.

Gemessen, beide Piloten, Sitzungsinstanz **und** gebundenes Kind:
```
curl --fail https://example.com/x.json
-> rc 2  [team-kit gate_dispatch] the session instance may not classify a failed run. …
```
Die Falschalarm-Zeile des benannten Tests (`tools/test_hooks_v2.py:4768`) prüft nur `git status --short` — eine Zeile ohne `--f…`-Präfix, deshalb sieht der Test die Klasse nicht.

**Schwere: blockierend** (bricht eine Alltagszeile in jedem Kit-Projekt; `curl --fail` ist die Standardschreibweise).
**Minimalfix:** die Klassifikationsfrage nur für eine Zeile stellen, die den Kernel-Einstiegspunkt nennt (`scripts/harness.py` / `kernel.cli` — dieselbe Lesung, die andere Gates schon haben); die Präfix-Mechanik bleibt innerhalb dieser Bedingung.

### F3 — DEC-0107-Hookhälfte ist mit einer von der Shell zusammengesetzten Option umgehbar
Gemessen, beide Piloten, Sitzungsinstanz, **alle** Hooks rc 0:
```
a="--"; b="fail-class"; python scripts/harness.py evidence --kind test --result fail \
  --related TSK-1 "$a$b" mechanical        -> allowed (keine Verweigerung, dispatch rc 0)
```
Die Shell übergibt `--fail-class`; der Kernel schreibt die Klassifikation dann der **gebundenen Lease** zu — genau der Schreiber, den DEC-0107 fangen soll. Der Docstring (`gate_dispatch.py:222`) sagt „THE MECHANISM, NOT A SPELLING (DEC-0102 (2))" — die Messung widerlegt das, der Leser ist weiter ein Schreibweisen-Leser. Dieselbe Absolutbehauptung steht in drei Rollentexten: `dev-team/skills/quality-engineer/SKILL.md:154`, `research-team/skills/reviewer/SKILL.md:73`, `office-team/skills/project-auditor/SKILL.md:91` („refuses the command from anybody else, the PM included").

**Schwere: benannter Rest — muss aber in die Löcherliste** (gemessene, offene Kette; ein dritter Zustand existiert hier nicht).
**Minimalfix:** auf einer Zeile, die den Kernel-Einstiegspunkt nennt, ein unplatzierbares Wort (`$`, Kommandoersetzung) wie in `gate_write_scope` als „nicht lesbar → verweigert" behandeln — oder die drei Rollensätze und den Docstring auf das reduzieren, was gebaut ist.

### F4 — Zwei NEUE Rollentexte lehren eine `evidence`-Zeile, die argparse ablehnt (versteckt hinter einem fremden Rot)
`team-kits/dev-team/skills/quality-engineer/SKILL.md:151-152` und `team-kits/research-team/skills/reviewer/SKILL.md:71-73`.
Gemessen, `tools/test_hooks.py::test_every_evidence_command_a_text_spells_names_every_argument_the_cli_requires`:
```
team-kits\dev-team\skills\quality-engineer\SKILL.md spells an `evidence` call ` --kind test --result fail
 --fail-class mechanical --related <TSK-ID> …` that omits --artifact-ref, --run-command, --run-scope,
 --summary while only 0 of its flag names are built at runtime.
… dasselbe für research-team\skills\reviewer\SKILL.md
```
Bei `5ecf62a` trug jede der beiden Dateien **genau eine** (vollständige) `evidence`-Zeile (`git show 5ecf62a:…` Zeile 22 bzw. 21) — die beiden Funde sind neu aus dieser Runde. Das Protokoll meldet zu diesem Knoten nur „red at 5ecf62a … My BUG-0301 change does not alter its verdict"; die eigenen neuen Texte sind dort nicht genannt. Nach dem S4-Patch des Nutzers bliebe der Knoten wegen B rot.
**Schwere: blockierend, Fix billig.** Der office-Auditor-Text (`project-auditor/SKILL.md:91`) zeigt die richtige Form: die Flagge benennen statt eine abgeschnittene Zeile zu buchstabieren.

---

## Weitere Befunde (nicht blockierend, aber zu schließen oder zu schreiben)

### F5 — `euer_report.document_key` behauptet mehr, als der Bericht baut
`team-kits/office-team/templates/repo/scripts/euer_report.py:287`: „Everything in this report that says »Beleg« counts through here." Die Offene-Posten-Tabelle (`:498-503`) und die stdout-Zeile zählen weiter Zeilen. Gemessen mit **einem** unbezahlten Mischbeleg:
```
[euer_report] … written (3 paid entries, 2 open items)
| L2026-0004 RE-2026-0004 | Kaeufer GmbH | 2026-09-01 | 119.00 EUR |
| L2026-0005 RE-2026-0004 | Kaeufer GmbH | 2026-09-01 | 214.00 EUR |
```
Ein Beleg erscheint zweimal und wird als „2 open items" gezählt. **Fix:** entweder die offenen Posten über `document_key` gruppieren (Brutto summiert) oder den Satz auf die zwei Stellen verengen, die wirklich durch den Leser gehen.

### F6 — „eine Eigenschaft des Hook-Seins" ist eine Aufzählung ohne Stolperdraht
`team-kits/*/hooks/_compat.py` (Konstruktionskommentar über `start_the_deadline`, und der Arming-Kommentar in `load()`): „every shipped hook … whose `load()` every shipped hook calls … turns the bound from a list of hooks that remembered to ask for it into a property of being a hook." Heute wahr (eigene Messung über alle drei `hooks/`-Verzeichnisse: 0 Hooks ohne `load`/`run_gate`/`payload`-Weg), aber **kein Test** hält es: ein neuer Hook, der stdin selbst liest, fährt unbewaffnet und nichts wird rot. Hausregeln 1 und 4. **Fix:** ein Test über die drei Hook-Verzeichnisse (30 Zeilen, meine Messung ist die Vorlage).

### F7 — Zahl an zweiter Stelle (klein)
`office-team/skills/office-manager/SKILL.md:295` „refuses **three** shapes that are harmless" — dieselbe Zahl steht in `DEC-0109` (`context:`). Zeiger statt Zahl.

### F8 — für den Lead (B hat korrekt als Seam übergeben, blockiert aber die Runde)
`docs/office/invoice-app-docking-point.md:60-61`, `:141`, `:240` lehren weiter „zwei USt-Sätze → Buchung von Hand"; die ausgelieferten Skripte akzeptieren sie seit DEC-0108 und liefern `booking.rows` statt `booking.ledger_add`. Eine App, die der Vertragsseite folgt, liest einen Schlüssel, den es bei Mischbelegen nicht mehr gibt. Die Seite muss vor dem Merge nach.

---

## Negative Befunde — GEMESSEN

- **H61/BUG-0153, Fenster:** 92/92 Einträge tragen `timeout` (dev 32, office 31, research 29; Werte 120 ×90, 1800 ×2). Fail-closed-Leser bindet als echter Prozess: Fenster 1.5 s → rc 2 („not enough time"), Eintrag ohne `timeout` → rc 2 („no entry that names it states a `timeout`"), 120 → rc 0.
- **Rot ohne den Fix, selbst reproduziert:** `start_the_deadline()` aus `_compat.load()` entfernt → `guard_no_adhoc` rc 0 in beiden Verweigerungsrichtungen (vorher rc 2); `tools/test_hooks.py -k never_imports_the_kernel` geht von **3 passed** auf **3 failed** und nach dem Zurücksetzen wieder grün.
- **Fenster ehrlich:** alle 31 dev- / 30 office-Einträge antworten weit innerhalb ihres Fensters; langsamster echter Prozess 0,63 s (`session_status.py`, SessionStart). `gate_pipeline` behält 1800 > eigenes Kind-Limit 1500.
- **Laufzeit gate_dispatch:** Zeile ganz ohne lange Option 0,12–0,20 s; Zeile mit *irgendeiner* langen Option 0,24–0,30 s. Der Kernel-Import wird also von jeder Zeile mit `--wort` bezahlt, nicht nur von einer mit dieser Option — B's „0,12–0,16 s" gilt nur für den Fall ohne lange Option.
- **DEC-0107, Verweigerungsrichtungen:** `--fail-class mechanical`, `--f mechanical`, `--fail-cl`, `--fail-class=…` von Sitzungsinstanz und von ungebundenem Kind → rc 2, beide Piloten.
- **DEC-0108:** Einzelsatz-Beleg unverändert (eine Zeile, `ledger_add` rc 0). Mischbeleg 100 @ 19 % + 200 @ 7 %: zwei Zeilen `--net=100.00/--vat-rate=19/--gross=119.00` und `--net=200.00/--vat-rate=7/--gross=214.00`, **eine** Rechnungsnummer, `ledger_add` rc 0 ×2, `--validate` rc 0; dieselben Zeilen ein zweites Mal gebucht → rc 1 (Dublette je Satz greift); EUeR-USt 33,00 korrekt aufsummiert. Unlesbare Bemessungsgrundlage einer Gruppe → rc 2 mit Satz; Mischbeleg, dessen Gruppen nicht rekonzilieren → rc 2; Widerspruch im Steuer-Dreiklang → rc 2 (BR-CO-15).
- **BUG-0300 / BUG-0301 (C's Nähte):** beide Knoten können scheitern — `_evidence_call_findings` auf die erste Fassung zurückmutiert → 1 failed; `_cannot_return` auf „exits somewhere" (If-Zweig) mutiert → 1 failed an `tools/test_hooks.py:9409`. Danach wiederhergestellt, beide grün. (Meine erste Mutation am Vorfilter war die falsche Stelle und blieb grün — das ist meine Fehlmessung, nicht die des Umsetzers.)
- **Spiegel:** über alle Dateien in `hooks/` der drei Kits abweichend nur `session_status.py`, `format_on_write.py`, `document_trays.txt`, `ENFORCEMENT.md` — genau die `KIT_SPECIFIC_HOOKS`-Namen.
- **ruff** über `team-kits/ tools/`: All checks passed. `tools/test_context_budget.py tools/test_role_contracts.py`: 78 passed, 1 skipped (29 s) — Deckenwert und Rollenverträge halten.
- **EVD-0425..0430** existieren, `result: pass`, `run_command` je ein Knoten-Id.

## Negative Befunde — NICHT GEMESSEN

- Die Annahmerichtung von DEC-0107 (gebundenes QA-Kind → rc 0): nur B's Testzeile, von mir nicht als Prozess nachgefahren (Lease-Aufbau).
- Die Batch-Zeile `request-approval verification --batch …` (B's Trockenlauf, 0 refused) — nicht wiederholt.
- Die drei stempelabhängigen Roten (`test_presets`, `test_reference_skills` [bash]/[powershell]) — nicht gefahren; Stempel ist Sache des Merges.
- Volle Suite, `bump_kit_version.py`, Strom A (Kernel) und dessen Hälften von BUG-0260/BUG-0302.
- Codex-Pfad der Deadline-Verweigerung: `_compat.start_the_deadline` ruft `stop(msg, "PreToolUse")` auch für Hooks auf Post/SubagentStop-Ereignissen; unter `TEAM_KIT_PROVIDER=codex` wäre dort das JSON-`decision: block` erwartet, nicht rc 2. Beobachtung, nicht gemessen.

## Lesedisziplin (Kosten, offengelegt)

Ganz gelesen habe ich: die Diffs von `_compat.py`, `gate_write_scope.py`, `gate_dispatch.py`, `invoice_intake.py`, `euer_report.py`, `ledger_add.py`, `finance_dashboard.py` und der vier SKILL.md (die geänderten Teile sind der Prüfgegenstand). Vom Protokoll habe ich Gliederung, Zeilen 130–278 und die Runs-Tabelle gelesen, nicht das Ganze.

## Was blockiert was

- **Runde blockiert:** F1 (H214 offen, drei gemessene Schreibweisen), F2 (Falschalarm `curl --fail`), F4 (zwei neue Rollentexte lehren eine abgelehnte Zeile), F8 (Vertragsseite widerspricht dem ausgelieferten Code).
- **Als benannter Rest in die Löcherliste, wenn nicht geschlossen:** F3 (zusammengesetzte Option) — mit Mechanismus („ein Wort, das die Shell erst herstellt, erreicht den Parser, ohne dass dieser Leser es sieht"), nicht mit meinen zwei Schreibweisen.
- **Nacharbeit ohne Blockade:** F5, F6, F7.