# Prüfbericht TSK-0136 — Runde 1 (kurz, gezielt) — **FAIL**

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead unverändert hierher gelegt (2026-09-11 10:0x,
Uhr gelesen). Kopie ohne `.git` unter `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0136\verify\repo` (`git init`
dort, weil `test_model_ladder.tracked_kit_files()` git fragt). Eigenes Rig `…\verify\vrig.py` (verweigert außerhalb des
eigenen Verzeichnisses, `newline=""` beidseitig, jeder Revert per sha256), Bericht `…\verify\vrig-report.json`. Uhr
gelesen 09:40:44 und 09:59:29.

## Befunde

### F1 — BLOCKIEREND (Code + Texte): die Eskalation läuft am Deckel RÜCKWÄRTS
`team-kits/kernel/dispatch.py:2949` — `on_this_rung = int(failed_runs) % per_rung`. Sobald `chosen` am `top` hängt,
wird kein Sprossenschritt mehr gewährt, der Effort-Reset läuft aber weiter am **abgeleiteten** Zyklus. Gemessen
(shipped dev-ladder): `FAIL 5 -> fable xhigh | FAIL 6 -> fable high`; office: `FAIL 5 -> opus high | FAIL 6 -> opus
medium`. Der 7. Lauf ist strikt schwächer als der 6. — genau die Asymmetrie, die R8 für den SATZ repariert hat
(`:2959-2963`), auf der Effort-Achse aber steht. Fünf ausgelieferte Texte behaupten das Gegenteil (`dispatch.py:2940`,
die drei `ladder.yaml`, die Verfassungsabsätze dev `:417` / research `:389` / office `:466`). Kandidatenfix, gemessen
(39 passed in `test_ladder`, Folge monoton): `granted_rungs = rungs.index(chosen) - rungs.index(start)`;
`on_this_rung = int(failed_runs) - granted_rungs * per_rung`. **Minimalfix:** diese zwei Zeilen + eine Zeile im
Rot-zuerst-Test `test_a_failed_run_raises_the_effort_before_it_raises_the_rung`, die über den Deckel hinausläuft.

### F2 — Prosa: der Kommentar über die synthetische Leiter beschreibt eine andere Leiter
`tools/test_ladder.py:251-253` („four effort steps … six rungs") gegen die Deklaration `:254-258` (drei Sprossen, drei
Effort-Schritte). **Fix:** Zahlen richtigstellen — oder die Fixture wirklich sechs Sprossen geben (dann fiele F1 im Test
auf).

### F3 — Prosa: die Messung zum entfernten Vokabular reproduziert nicht
`tools/test_hooks.py:6090-6092` behauptet „NO shipped text"; gemessen: `no team-size question` trifft
`office-manager/SKILL.md:94`. Folgenlos für den Leser (Subjekt „team-size" mit Bindestrich, kein Ask), falsch ist die
Messbehauptung. **Fix:** Teilklausel.

### F4 — Prosa: das Zitat in `harness-lead.md` stützt die Gegenthese
`.claude/agents/harness-lead.md:13-15` sagt, `.claude/agents/` werde beim Sitzungsstart gelesen; `CLAUDE.md:186` sagt
an der zitierten Stelle das Gegenteil (Rollendateien werden bei jedem Aufruf frisch gelesen). Die Schlussfolgerung (das
Modell der SITZUNG bleibt bis zum Neustart) stimmt. **Fix:** auf die `agent:`-Bindung abstellen.

### F5 — blockiert die EVD-Erfassung: Protokollzahlen
`protocol.md:88` und `:160` sagen Stempel `-6`, gemessen `-7` ×3 (Kopfzeile `:3` sagt selbst -7); `:166` „8 of 8 rows
… 7 of 7 nodes" gegen `:59` / `rig-report.json`: **9 Zeilen, 8 Knoten**. Das sind die EVD-Summary-Zeilen. **Fix:** drei
Zahlen (−7, 9/9, 8/8) + §4.

## Negative Befunde — gemessen
Sechs Suiten voll grün (39 / 13 / 26 / 32 / 27 / 5), ruff/validate grün, `bump_kit_version` unchanged ×3; R2a/R8
nachgestellt; zehn eigene Mutationen rot (office `build: opus`; dev `design: top`; Lesedisziplin zweimal; ein Wort
Drift im geteilten Absatz; office-manager auf `worker`; research-Absatz nennt `fable`; Kernel ohne Remainder-Reset;
Kernel ohne Kit-Deckel; Klassenwort klein; office-Absatz behauptet eine Sprosse); geteilter Absatz `d696f71a18629eca`
×3 (912 B); `validate.py` verweigert das Alias-Ziel (`lead` ist die einzige Schreibweise); Residuum 5 bestätigt
(`--rung sonnet` → opus in dev, sonnet in office); Residuum 6 bestätigt (office FAIL 1 hebt medium→high); Residuen
1, 2, 3, 4, 7, 8 ehrlich — es sind **neun**; Leser dev 1/37, research 1/37, office 1/33; Paketgrößen stimmen; kein
Mischversions-Pfad (der globale Store steht auf 2026.09.02-10 ohne `ladder.yaml`). `test_model_pins` bleibt bei einem
`fable`-PM-Pin grün — das „rot" trägt allein `test_role_contracts` (Oder-Formulierung, kein Befund).

## Nicht gemessen
Keine echten Hook-Prozesse gegen ein selbst gebautes Projekt (Zeile (c) nur über `test_light_kit` + R6); kein voller
`tools/`-Lauf; `harness-lead.md` `model: opus` von innen nicht messbar; (g)-Zahlen nicht nachgerechnet; DEC-0095 (1)
„every kit" gegen „office unchanged" nicht geprüft (Lead-/Nutzerentscheidung).

## Urteil
**FAIL.** F1 blockiert die Runde (Mechanismus: der Effort-Reset hängt am abgeleiteten Zyklus statt an den gewährten
Sprossenschritten; Fix und Rot-Zeile je eine Zeile); F5 blockiert die EVD-Erfassung; F2–F4 sind benannte Restposten
für dieselbe Nacharbeit.
