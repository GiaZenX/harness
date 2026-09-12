# Prüfbericht TSK-0139 — Runde 2 (F1–F8 + die zwei TSK-0138-Regressionen) — **FAIL (nur F3, eng begrenzt)**

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead hierher gelegt (2026-09-11 23:5x, Uhr gelesen).
Gemessen 23:38–23:54 in eigenen Kopien (aufgefrischt), Pilot neu bespielt (`gate_git.py` md5 `e5dc0f31…` = Repo).
Repo unberührt (`.audit/hook_events.jsonl` md5 `92d2f0d7…` vor/nach).

## F1 — PASS (26 Prozesszeilen auf dem Piloten)
A rc 0 mit OWED-Note; B/C/D rc 2; E rc 2. Eigene Angriffe: `feat:refs/heads/main` rc 2 · `:main` rc 2 · zwei
Refspecs, eine nennt das Item rc 2 · `--mirror/--tags/--delete/-d/--follow-tags` rc 2 · `-u origin HEAD:main` rc 2 ·
`--push-option=… HEAD:main` rc 2 · `--receive-pack=… HEAD:main` rc 2 · `HEAD:main --force-with-lease` rc 2 ·
`-o main origin feat/…` rc 0 (Optionswert kein Ziel) · bare `git push` rc 0 · `main:feat/PR-0001-x` rc 0 ·
`HEAD:refs/heads/PR-0001-fix` rc 0 · `HEAD:$BR` / `HEAD:mai*n` / `HEAD:$(cat .br)` rc 2 (fail-closed).
`_SPREADS_PAST_ITS_REFSPECS` mit beidseitigem Stolperdraht (toter Eintrag → declared-only; fehlender `-d` → rot).

## F2 — PASS an Anfrage UND Prägung (eigene Kette, echter Kernel + Hook)
Knoten existiert nirgends → REFUSED „resolves to no test in this checkout"; Id nur im Body-Kommentar → REFUSED
„none of those tests NAMES BUG-0003 where a reader looks"; erster Docstring-Absatz → ASKED. MINT: gute Evidenz,
danach neuere nicht-nennende EVD, Klick → „no approval was created … 1 of its items moved", Item bleibt TRIAGED.
`proofs_naming`: „nur bestandene" → `…closes_nothing_at_all` rot; indirekter Hop erlaubt →
`test_a_parent_defect_is_not_closed_by_its_childs_green_run` rot; coverage_blocker aus → 3× DID NOT RAISE.

## F8 — PASS
Fünf EVDs (BUG-0010/0052/0075/0082/0092 → EVD-0284/0298/0306/0312/0314): pass, selection, alle Knoten existieren
und nennen den Fehler am erklärten Ort, `related` direkt. Die vier Stapelzeilen auf einer Kopie: ACCEPTED ×4, 31 Ids.
(BUG-0075 trägt drei nennende EVDs; „elf mit zwei" ist Prosa.)

## F3 — FAIL, nicht behoben (`tools/test_hooks.py:14186-14191`)
Unter PowerShell (`shutil.which("bash")` = WSL) weiterhin rot: „Templates not found: /home/giazenx/…"; unter Git
Bash 2 passed. Der Fix repariert die Schreibweise, nicht den Transport: `export HOME`, `WSLENV=HOME/u`, `env` — der
WSL-Launcher setzt `$HOME` aus `/etc/passwd`; `test -d /mnt/c/…` rc 0 (die Übersetzung wäre gültig, kommt nur nicht
an). Blockiert **eine Id**: BUG-0067 (Stapelzeile 3). Minimalfix: prüfen, ob diese bash ein übergebenes `HOME` trägt,
sonst `pytest.skip`.

## F4/F5/F6 — PASS (je Mutation rot; F6 Gegenende hält). F7 — ehrlich (55 Stellen ohne Literal, identisch; 67 statt
65 gesamt, tragende Zahl stimmt). Zwei TSK-0138-Regressionen — PASS (1 passed / 1 passed).
Stempel unchanged -22/-22/-21; Spiegel `e5dc0f31…`/`16b0cd7c…`/`a44623dc…`; Absätze ×3; ruff/validate grün;
`test_close_measured_pass` 12, `test_approvals_dispatch` 217, `test_hooks -k "git or push or seeding"` 149 passed / 1
failed (= F3).

## Nicht gemessen
Kein Volllauf; die übrigen Module der Rework-Läufe; die drei Order-3-Roten nicht erneut gefahren.

## Verdikt
**FAIL nur wegen F3.** Klicks 1, 2 und 4 sind sicher; **Klick 3 wartet** oder BUG-0067 wird herausgenommen.
