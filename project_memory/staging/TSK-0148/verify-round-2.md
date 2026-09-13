# Prüfbericht TSK-0148 (PR-0012, Order 4, Strom C) — Runde 2 — **PASS**

Prüfer: `harness-verifier` (Opus, high), 3 min, +17 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-13 00:26, Uhr gelesen). Rest: drei veraltete Zeilenzeiger in docs/holes/H215.md (Zielrunde: auf Funktionsnamen umstellen).

## Prüfbericht TSK-0148 / Strom C — Runde 2 (schließend): **PASS**

Neuer Snapshot (3043 Dateien, Rig `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0148\verify\snapshot.py`), read-only gegen das Repo, nur die vier Punkte gemessen.

### B1 — behoben, Tabelle hält gegen meine eigene Sonde

`tools/test_repo_hygiene.py:2817` sagt jetzt *„THE QUESTION IS BINDING BY ASSIGNMENT … the three ASSIGNMENT spellings"* und trägt einen eigenen Absatz *„WHAT THIS DOES NOT REACH"* mit Zeiger auf `docs/holes/H215.md`. Die fünf Zeilen der H215-Tabelle habe ich gegen eine selbst geschriebene Sonde nachgemessen — **alle fünf stimmen, Richtung eingeschlossen**:

```
r1_with_as                                 silent
r2_for_target                              silent
r3a_double_binding_real_start_silent       silent
r3b_double_binding_false_report            REPORTED
r4_name_from_another_name                  silent
r5_program_as_a_parameter                  silent
control_hooks_path_as_an_argument          silent
```

Auch der Fehlalarm-Satz reproduziert exakt: `shipped reader, forgetful: 0` / `widened reader, forgetful: 1` → `tools/test_hooks_v2.py 13964 test_trust_cannot_be_reset_by_re_running_the_recorder`. Der widerlegte Satz („beide melden nichts statt falsch zu melden") steht als widerlegt drin — das ist die Richtung, die ich sehen wollte.

**Kleiner Rest, nicht blockierend:** `docs/holes/H215.md` nennt die vier Hop-only-Stellen noch mit `tools/test_hooks_v2.py:13537`, `:14600`, `tools/test_repo_hygiene.py:2682`. Heute gemessen: `['tools/test_hooks_v2.py:13626', 'tools/test_hooks_v2.py:14689', 'tools/test_repo_hygiene.py:2683', '.claude/hooks/test_gates.py:344']` — drei von vier Zeigern sind durch die Nachbarströme veraltet. Zeiger, kein Schutzversprechen; gehört beim Rundenabschluss nachgezogen oder auf Funktionsnamen statt Zeilennummern umgestellt.

### B2 — behoben, und ehrlicher als gefordert

`project_memory/staging/TSK-0148/dec-question-BUG-0296.md`: Empfehlung **zurückgezogen** („Keine Empfehlung — und warum das hier die ehrliche Antwort ist"), C ausdrücklich auf die Runden 3 und 4 begrenzt, mit einer Vier-Zeilen-Tabelle und der sauberen Begründung („ein **fehlendes** Wort erzeugt kein ‚unentscheidbar', sondern ein selbstsicheres ‚hier wird gar nicht verneint'"). Die Fehlalarm-Kosten von C stehen als **ungemessen** da, und die zwei Messungen, die eine Empfehlung erst erlauben würden, sind benannt. Der alte Fehler wird offen eingeräumt.

Die eine neue Sachbehauptung darin habe ich nachgemessen — sie stimmt:

```
Ohne den Fix wird ein Test rot          names_a_test=True
Without the fix a test goes red         names_a_test=True
Das Ergebnis wird ohne den Nachweis der Tests rot   names_a_test=True
```

Lesbarkeit für einen Nicht-Entwickler: gegeben — Alltagssprache, jeder Fachbegriff am Beispiel erklärt, die Entscheidung auf A/B/C reduziert.

### B3 — Zahl weg

`tools/test_repo_hygiene.py:1310-1313`: die Meldung sagt jetzt „*those are the sites the defect did NOT touch*" ohne Zahl; Sinn erhalten. Kein weiterer wachsender Zähler im geänderten Abschnitt (die einzige verbliebene Zahl dort ist der Zeiger `model_tiers.yaml:31`, bestandsalt).

### B4 — Zeilentabelle da, Zählung stimmig

`protocol.md:137` trägt „## Rows -- ONE line each, as `expected_outputs` asks" mit allen sechs Spalten für sechs Zeilen (BUG-0295/0297/0299/0296/0300/0301); die Prosa-Abschnitte bleiben als Detail. COUNTS und Naht-Abschnitt sind versöhnt (2 Nähte an B + 1 an den Lead, letztere als erledigt vermerkt).

### Abschlussmessungen (eigene Kopie)

- `ruff check tools/test_repo_hygiene.py .claude/hooks/test_gates.py` → **All checks passed!**
- Die beiden Namensknoten von EVD-0417/0418 plus die Haken-Start-Fege: **3 passed in 13,38 s**.
- Prosa-/Assertions-/Index-/Zeigerleser: **3 passed, 1 skipped** (6,3 s) — der Loch-Index ist grün.
- Nicht neu gefahren: `.claude/hooks/test_gates.py` (im Rework nicht berührt — die Begründung des Umsetzers trifft zu, die BUG-0297-Dreirichtungsmessung aus Runde 1 bleibt gültig), volle Suiten (verboten), Ströme A/B.

### Urteil

**PASS.** Beide blockierenden Befunde sind als Text geschlossen, ohne Verhaltensänderung, und beide Tabellen halten gegen meine eigenen Sonden statt gegen ihre eigene Prosa. Offen bleibt genau eines, als benannter Rest für den Rundenabschluss: die **drei veralteten Zeilenzeiger in `docs/holes/H215.md`** (Mechanismus: Zeilennummern in Prosa altern, sobald ein Nachbarstrom dieselbe Datei schreibt — die Abhilfe ist, auf Funktionsnamen zu zeigen, nicht diese drei Zahlen zu korrigieren). BUG-0297 bleibt wie bestellt rot und ohne EVD, bis der Nutzer den S4-Patch fährt.