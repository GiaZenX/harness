# Prüfbericht TSK-0139 (PR-0012 AC-3) — Runde 1 — **FAIL**

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead hierher gelegt (2026-09-11 22:1x, Uhr gelesen).
Gemessen 21:30–22:09 in `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0139-verify\` (`work` ohne `.git`, `clone`
mit Historie, saubere Klone `head-fd7e2fa` / `head-07691ba`, eigener dev-team-Pilot). `.audit/hook_events.jsonl`
md5 `92d2f0d7…` vor und nach allen Läufen. Rig verweigert fremde Arbeitsverzeichnisse, binär.

## Befunde

**F1 — BLOCKIEREND (hoch): der BUG-0081-Fix macht einen Push auf den Trunk zur Arbeitszweig-Veröffentlichung.**
`team-kits/{dev,research}-team/hooks/gate_git.py:344-356` (`_publishes_a_work_branch`), Leser `target_items` `:123`
liest nie das Push-ZIEL, sondern Ids im Segment oder den aktuellen Branch. Prozess (PR-0001 APPROVED, test+review
pass, keine acceptance): A `git push origin feat/PR-0001-x` rc 0 (Note OWED) · **B `git push origin HEAD:main` rc 0** ·
**C `feat/PR-0001-x:main` rc 0** · **D `git push --all origin` rc 0** · E `git merge` rc 2. Vor dem Fix B/C/D rc 2.
Docstring `:350` behauptet das Gegenteil. Fix: Refspec-Ziel lesen; Trunk / `--all` / `--mirror` nicht mildern.

**F2 — BLOCKIEREND für den Klick (hoch): die Stapelroute prüft die „nennt den Fehler"-Hälfte nicht.**
`kernel/approvals.py:1098-1113` (`batch_walk_blockers`), `:1130-1175` (`verification_batch`) prüfen Art=test,
Ergebnis=pass, `related`. Prozess: BUG-0001 TRIAGED (nie FIXED) + `evidence --kind test --result pass --related
BUG-0001 --run-command "… tools/test_unrelated.py::test_something_else"` → `request-approval verification --batch`
rc 0 → Klick → APR-0002, BUG-0001 VERIFIED, archiviert. Die Namensprüfung lebt nur in
`tools/close_measured_pass.py::nodes_naming`. Fix: Ableitung in den Kernel, Verweigerung nach Namen an Anfrage
UND Prägung.

**F3 — BLOCKIEREND für BUG-0067: Test rot bei `bash` = WSL.** `tools/test_hooks.py:14024/14063` übersetzt den
Skriptpfad, nicht `HOME`: PowerShell (`C:\WINDOWS\system32\bash.EXE`) 1 failed „Templates not found:
/home/giazenx/…", Git Bash 1 passed. Docstring „only a host with no bash at all is out" falsch.

**F4 — Prosa/Loch:** Merge-Klausel des BUG-0081-Fix ungetestet (Mutation grün); tragend nur für `git $CMD origin …`
(rc 0 ohne Klausel), das keine Zeile misst. **F5 — Prosa:** `tools/test_report.py:2859` polaritätsblind („FIVE
AskUserQuestion" besteht). **F6 — Prosa:** `tools/test_role_contracts.py:2019` `\bnot\b` gilt für den ganzen Satz
(„…which is not optional…" besteht). **F7 — Loch:** `tools/conftest.py:82-84` — eine Hook-Aufrufstelle ohne eigenen
`CLAUDE_PROJECT_DIR` urteilt über den leeren Ambient-Baum (`git merge` rc 0 still); kein Test verlangt die
Nennung. **F8 — Voraussetzung fehlt:** 0 von 31 EVDs existieren (EVD-Spalte „lead"); die Frage kann nicht gestellt
werden.

## Punkt für Punkt
BUG-0081 FAIL (F1, F4) · BUG-0053 PASS (4 Kontrollen + `-p=other` und `env NAME=…` rc 2; gegen Docker 29.4.2
gemessen: Flags nach dem Verb sind ungültig — meine erste Hypothese war falsch) · BUG-0052 PASS (Köder-Log
byte-identisch; Rot-zuerst unter Sitzungsbedingung rot; Rest F7) · BUG-0082 PASS (`?`/`[...]` in erster/mittlerer/
Blatt-Komponente rc 2; `pytest tests/test_*.py` rc 0) · 0074/0075/0076/0058 Zusicherungen messen den Defekt ·
Rot-zuerst 4/5 (0067 = F3) · eigene Mutationen 5/6 (0081 grün = F4) · 5 aus 16 „schon behoben" PASS (Nennung im
ersten Docstring-Absatz, Zusicherung misst den Item-Defekt) · BUG-0055/0056 Ausnahmen ehrlich (F6 schwächt leicht)
· 5 vorbestehende Rote bestätigt, **Besitz gemessen**: bytecode + Freigabetexte grün auf 07691ba → Regressionen von
TSK-0138; Lead-als-Subagent, Pins (auf 07691ba schon rot) und research chain älter · 9 Regressionen PASS
(`-k trust` 13, `test_migrate` 143 im Klon) · Stempel unchanged -21/-21/-20, ruff/validate grün, Hand-Absatz
`24a8ccaf…` ×3, Lese-Absatz ×3, Kit-Spiegel byte-identisch · EVD FAIL (F8).

## Eigene Irrtümer / nicht gemessen
Erster `test_migrate`-Lauf rot = Kopie ohne `.git` (Fixture braucht Historie). Kein Volllauf; research chain auf
07691ba nicht gemessen; `.ruff_cache` in `templates/repo/` beim Erstinstall ungemessen; 26 weitere „schon behoben"
und 10 Rot-Zeilen nicht gefahren; `conftest.py` ganz gelesen.

## Verdikt
**FAIL.** F1 (Trunk-Push ohne Abnahme), F2+F8 (Stapelroute) blockierend; F3 blockiert BUG-0067; F4–F7 Prosa/Löcher.
Die Stapelroute ist für die 31 Ids heute nicht sicher.
