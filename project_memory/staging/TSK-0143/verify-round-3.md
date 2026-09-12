# Prüfbericht TSK-0143 (PR-0012, Order 3b, Strom C) — Runde 3 — **PASS**

Prüfer: `harness-verifier` (Opus, high), 8 min, +33 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 12:56, Uhr gelesen). N1 beim Capture korrigiert; N2 (eine Docstring-Zeile) → Zielrunden-Auftrag; N3 vom Lead im Listen-Dokument vermerkt.

## Prüfbericht Runde 3 — TSK-0143 (Strom C), Nacharbeit R1/R3/R4 + Selbstfund

Neuer Schnappschuss `…\verify\tree3` (2913 Dateien, ohne `.git`), Rig `…\verify\rig3.py`. Im Repo nur gelesen. Vom Protokoll nur „Rework 2" (Zeilen 547–665).

### R1 — geschlossen, beide Installer

* Meine eigene Pflanzung aus Runde 2, `team-kits/scaffold_team.sh:284` (die Zeile, die das Skript nach `.claude/HANDOVER_PENDING` schreibt) → **1 failed in 4,60 s** (Runde 2: 2 passed, grün).
* Der PowerShell-Zwilling, `team-kits/scaffold_team.ps1:272` → **1 failed in 5,78 s**, gemeldete Zeile: `team-kits/scaffold_team.ps1:272 DEC-9142 (in a line this script writes out)`.
* **Die beiden Schranken sind wahr und kosten heute nichts.** Selbst gemessen über alle `.sh`/`.ps1` unter `team-kits/`: `DEC-Ids gesamt: 9 | vom Shell-Leser: 4 | vom Prosa-Leser: 5 | von keinem: 0`. Die „eine Zeile"-Schranke schneidet auf diesem Baum nichts ab, und `Spannen mit Backtick UND Id: 0` — die fehlende Backtick-Ausnahme erzeugt keinen Fehlalarm. Die Shell-Hälfte hat ihren eigenen Boden (`assert spoken >= 2`), ein verstummender Leser wird also rot, nicht still.
* `docs/holes/H73.md:21-33` nennt beide Leser, beide Zahlen (69 Python-, 4 Shell-Zitate), das Rot-zuerst-Paar und den Test; Urteilszeile `:60` „**(a) GESCHLOSSEN (TSK-0143), der Rest bleibt Rest**", (b)(c)(d) bleiben als ausgewiesene Grenzen stehen. EVD-0391: 9 Knoten, `naming=[…test_a_decision_named_in_a_message_a_user_reads_is_one_that_resolves]`, `blocker=''`.

### R3 — erledigt

EVD-0392 trägt die Neun-Knoten-Zeile **einschließlich** `tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` (dem Knoten, dessen Sweep die zitierten 625/680 erzeugt), benennt BUG-0263, `blocker=''`. Selbst nachgefahren: **7 passed, 2 skipped in 118,93 s** (die zwei Skips sind die git-gestützten Knoten — meine Kopie hat keinen Index; in Runde 1 mit Index grün gemessen).

### R4 — die Messung stimmt auf die Stelle genau

Eigene Nachrechnung über die ausgelieferten `.py`: `DEC-Ids in Docstrings: 190 | vom Prosa-Leser beurteilt: 184 | von niemandem: 6`, und die sechs sind exakt die benannten — `guard_memory_budget.py:33` in allen drei Kits (`DEC-2100`), `kernel/migrate.py:1291` (`DEC-0000`), und die zwei echten: `team-kits/kernel/dispatch.py:204` (`DEC-0091`) und `team-kits/office-team/templates/repo/scripts/invoice_intake.py:370` (`DEC-0075`), beide im Wortlaut wie im Payload zitiert; beide Entscheidungen liegen in `decisions/active/`. Der deutsche Satz ist klar, mit echten Umlauten und ohne Fachjargon.

### Selbstfund — gebaut und rot-fähig

`tools/test_repo_hygiene.py`, `UNREADABLE` als dritte Antwort in `_defined_in`. Mutation `return UNREADABLE` → `return None` → **1 failed in 1,95 s** (`assert None is <object …>`). Der Test setzt `ROOT` per `monkeypatch` auf `tmp_path` und schreibt nur dorthin — im Baum stehen nach mehreren Läufen keine Streudateien (`test_whole.py`/`test_half_written.py` nicht vorhanden). Der Sweep zählt eine solche Datei nicht als Verstoß und nicht als Schweigen, sondern warnt sie namentlich.

### Verifikationszeile

Gegen eine Store-Kopie im Checkout neu gebaut: **rc 0**, neun Items, und der Kernel wählt die ablösenden Datensätze selbst: `BUG-0165 (EVD-0391); BUG-0263 (EVD-0392)`, die übrigen wie gehabt. `ruff check` über die fünf geänderten `.py`: **All checks passed**. Kein Commit (HEAD `10a5127`), keine Transition (BUG-0165 `TRIAGED`, BUG-0263 `OPEN`); der Diff an `team-kits/scaffold_team.*` stammt aus Strom B (`kit_repo_files.json`, BUG-0277) — C hat die Dateien wirklich nur gelesen.

---

### Kleine Restposten (nicht blockierend)

* **N1 — `project_memory/staging/TSK-0143/hole-docstring-dec-id.json`, Feld `limits`:** „Zwei Verweise auf **eine** Entscheidung" — es sind zwei Verweise auf **zwei verschiedene** Entscheidungen (DEC-0091 und DEC-0075). Ein Wort, aber es ist der Satz, den der Nutzer beim Aufnehmen des Lochs liest. Beim Capture ändern.
* **N2 — `tools/test_repo_hygiene.py`, erste Docstring-Zeile von `_defined_in`:** „…, or `None` when there is no such file" — es gibt jetzt drei Antworten; die dritte steht erst zwei Absätze weiter. Wer bei Zeile eins aufhört, nimmt den alten Vertrag mit. Eine Zeile.
* **N3 — offen beim Lead, von beiden Seiten benannt:** der Absatz „BEFORE THE BATCHES" in `limits-update-lines.md` behauptet weiter, die 14 OPEN-Items bräuchten zuerst `transition … TRIAGED`. C verteidigt den Satz ausdrücklich nicht; meine Messung aus Runde 2 (`batch_walk_blockers → []` für OPEN, bei beiden Arten) steht dagegen. Entweder Absatz streichen oder meine Messung danebenschreiben — nicht 14 Transitionen blind fahren.

## Urteil: **PASS**

R1 ist an beiden Installern gemessen geschlossen, mit einer Schranke, die gemessen nichts durchlässt; R3 und der Selbstfund sind sauber gebaut und gehen unter meinen eigenen Mutationen rot; R4 ist als Loch-Payload mit einer auf die Stelle genau reproduzierbaren Messung übergeben statt in der letzten Minute angefasst. N1 und N2 sind je eine Zeile, N3 ist eine Zustandsfrage des Leads.

Pfade: `C:\Offline Repos\AgentAndSkills\tools\test_repo_hygiene.py`, `C:\Offline Repos\AgentAndSkills\docs\holes\H73.md`, `C:\Offline Repos\AgentAndSkills\project_memory\staging\TSK-0143\hole-docstring-dec-id.json`, `C:\Offline Repos\AgentAndSkills\project_memory\staging\TSK-0143\limits-update-lines.md`, Prüfstand `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0143\verify\` (`rig3.py`, `check_naming3.py`, `dry_check_lists3.py`, `tree3\`).