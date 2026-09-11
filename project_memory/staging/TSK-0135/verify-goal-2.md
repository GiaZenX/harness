# Kurze Runde 2 — TSK-0135 / PR-0011 — **PASS**

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead unverändert hierher gelegt (2026-09-11 08:5x,
Uhr gelesen).

Kopie ohne `.git` unter `…/TSK-0135/verify/goal2/repo` (`git init` danach, für `git ls-files`), eigenes Rig daneben,
ein pytest zur Zeit, kein Volllauf, Uhr je Lauf gelesen, **kein** Schreibzugriff ins Repo (SHA-Vergleich am Ende:
2400 = 2400 Dateien, **0 abweichend, 0 einseitig**).

## Urteil je nachgearbeitetem AC

| AC | Urteil | Gemessene Zeile |
|---|---|---|
| **AC-2** | **PASS** | `ac2a` RED · `ac2b` (Zwilling) RED · **`ac2c` („derived" im Satz) jetzt RED** · meine neue Schreibweise `ac2d` („…the **Ableitung** follows from his answer") RED — je `FAILED …::test_no_entry_file_and_no_lead_text_asks_the_user_for_the_team_size`. Carrier gemessen: `never ask` trägt 9 ausgelieferte Sätze, `not asked` 2, `removed the question` 2 — die gestrichenen `never asked`/`NEVER ask` waren tatsächlich Duplikate des `never ask`-Präfixes unter `IGNORECASE`. Docstring auf das gekürzt, was der Code baut („a vocabulary, so a wording outside it passes"). |
| **AC-4** | **PASS** | `ac4a` RED · **`ac4b` („…and this is not optional") jetzt RED** · **`ac4c` (deutsche Umschrift „Pruefer … kein Schritt") jetzt RED** — `Pr(ü\|u\|ue)fer` schließt die Umschriftlücke, die ich beim Zielrundenfix noch offen gelassen hatte · meine neue Schreibweise `ac4d` („A verifier round follows after each change; **no shortcut** is allowed here.") RED. |
| **AC-5** | **PASS** | Neuer Leser `test_both_entry_files_ask_the_same_first_contact_question_and_never_the_old_one`. `ac5a` (alte Frage im claude-Zwilling) RED · `ac5b` (im codex-Zwilling) RED · **meine eigene Probe `ac5c` (DRIFT: claude-Zwilling umformuliert zu „Akte, Entscheidungen, Belege … lieber erstmal frei?", codex unangetastet)** RED. Die Frage wird als **Form** aus der Anweisungsdatei gelesen, nicht im Test zweitgeschrieben; `_transliterated` faltet die ASCII-Fassung. |
| **AC-6** | **PASS als neu geschnitten** | Ich habe die Rohströme selbst gelesen, nicht die Zusammenfassungen: `probe-…081108.jsonl` 54 Records → 10 `tool_use` (Read/Read/Bash/Read/Read/Bash/Bash/Bash/Read/Bash), **0 `AskUserQuestion`**, `permission_denials: []`, `num_turns 11`, `end_turn`, Abschlusstext „**Sollen wir die Anforderung verfeinern, oder direkt zur Scope-Freigabe übergehen?**"; `probe-…081402.jsonl` 35 Records → 4 `tool_use`, **0 `AskUserQuestion`**, `num_turns 5`, `end_turn`, „PR-0001 ist bereit für die Scope-Freigabe…". Beide Male 8 System-/Hook-Records. Der Eintrag `headless_pm_stop_point` gibt das korrekt wieder, und die Protokollzeile behauptet **genau** das und nicht mehr: „vorbereitet + Grund gemessen + Lauf und Urteil sind Nutzerzeilen". Mein Zielrundenbefund B1 ist damit bestätigt **und** überholt: die Begründung war nicht nur unvermessen, sie war falsch — der PM bleibt nicht am Tor stehen, er erreicht es nie. |
| **AC-10** | **PASS** | Arithmetik gegen die eigene Tabelle nachgerechnet: 937/896 = 1,046 („rund 1,05×") ✔ · 937/630 = 1,49 („rund 1,5×") ✔ · 896+649+630+770 = **2945 k**, 937/2945 = 0,318 („rund ein Drittel") ✔ · 253/490 = 0,516, /656 = 0,386, /803 = 0,315 („ein Drittel bis gut die Hälfte") ✔ · Summe 1949 min, 253/1949 = 0,130 („ein Achtel") ✔ · 02:34→08:42 = **368 min**, 368/490 = 0,751, /656 = 0,561, /803 = 0,458, /1949 = 0,189 — alle fünf Werte des Absatzes stimmen ✔ · „Stand 04:58" ist weg ✔. Die Kernaussage ist umgedreht und ehrlich: „G6 ist teurer, nicht billiger" gegen einen Einzelstrom. |

**P-Zeilen:** P1 ✔ (`red_first-20260911-045313.log.json` liegt im Staging, 26 487 B, 41 Zeilen; EVD-Zeile und §3a
nennen sie, §3a führt beide Logs mit Zeilenzahl). P2 ✔ (§1a nennt die Zahl nicht mehr, sondern zeigt auf §3a; der
ausgelieferte Wert `1e6b941e1f45ab2a` steht einmal — der alte `ebfb2fcadea2855a` nur noch im **Rohprotokoll**, wo er
als Momentaufnahme hingehört). P3 ✔ und für beide Leser zutreffend: der AC-4-Docstring sagte die Grenze schon, der
AC-2-Docstring sagt sie jetzt, und §6 (4) trennt sauber „Vokabular-Natur bleibt" von „zwei Löcher *in* den
Vokabularen geschlossen". P4 ✔ (§0a nennt die registrierte Kette und den AC-Textfehler). P5 ✔ — und zwar in der
stärkeren Form: §0a sagt ausdrücklich, dass der AC-Wortlaut für die Anfrage-Id **nicht erfüllt ist und es nicht sein
kann**, solange `gate_approval.MARKER_RX` dort liest. P6-Zurückstellung **ist ehrlich**: sie nennt den Mechanismus
(Kernel-Datei → Kit-Hash → neuer Stempel → die zeichenweise vergleichenden Suiten), zitiert meine eigene Einstufung
„niedrig" und die Kostenregel DEC-0095 (6). P7 war bereits deutsch.

**Kit-Dateien unberührt:** `bump_kit_version.py` → `unchanged (2026.09.11-4)` ×3; `validate.py` all structural checks
passed; `ruff` All checks passed; die genannten Leser `-k "team_size or first_contact or cadence or rework or
free_text or entry"` über `test_light_kit.py` + `test_hooks.py`: **28 passed in 17,02 s**.

## Neu (nicht aus der Zielrunde), alles klein und nicht rundenblockierend

1. **Zwei tote Einträge bleiben im AC-2-Vokabular**, während der Kommentar daneben tote Einträge zur Regel erklärt
   („a dead entry in a vocabulary is the half of house rule 1 that rots quietly"). Gemessen: `nie gefragt` trägt **0**,
   `no team-size question` trägt **0** ausgelieferte Sätze; ihre Entfernung → `3 passed, 1018 deselected` (GREEN).
   `tools/test_hooks.py:6086-6088`. Fix: zwei Alternativen streichen — oder den Kommentar um die Zeile ergänzen, dass
   diese beiden absichtlich vorwärts stehen.
2. **Eine Zahl an zwei Orten, neu eingeführt:** §7 rechnet mit **368 min** (02:34→08:42, und alle fünf Verhältnisse
   passen dazu), die Rohprotokollzeile 08:42:33 sagt **362 min** für dieselbe Größe. Fix: die Rohprotokollzeile auf 368
   ziehen.
3. **`headless_pm_stop_point.run_1` nennt 64,9 s „of API time"** — der Rohsatz hat `duration_ms 64921` (Wanduhr) und
   `duration_api_ms 27464`. Der Wert stimmt, das Etikett nicht. Fix: „64,9 s Wanduhr (27,5 s API)".
4. **Außerhalb PR-0011, für den Lead:** `DEC-0095` (1)/(2) (Bauer- und Orchestrator-Standard **Opus**) ist beschlossen
   und in diesem Baum **nicht gebaut** — kein Kit-File hat sich bewegt, und mein office-Pilot misst weiter `class build
   starts on pin`. Die `sonnet/opus/fable`-Zeilen des Pilot-Rigs sind damit der Stand *vor* DEC-0095. Das ist der
   bekannte „beschlossen ≠ gebaut"-Fall dieses Repos und gehört als eigenes Item vor die nächste Runde, nicht in diese.
5. **AC-6, letzte Klausel, ehrlich benannt und trotzdem erwähnenswert:** „the builder default tier is decided **from
   it** as a DEC" — entschieden hat es `DEC-0095`, ausdrücklich **vor** dem Experiment und aus Kostenzahlen („der
   Nutzer entscheidet es jetzt, auf Kosten, vor dem Experiment"). Das steht so im Kontextfeld der DEC, ist also keine
   stille Umdeutung; der Experimentlauf bleibt eine Nutzerzeile.
6. P6 hat noch **kein FR-Item** — es lebt bisher nur in §6 (8). Eine Zeile für den Lead, damit es die Staging-Datei
   überlebt.

## Gesamturteil PR-0011: **PASS**

Alle zwölf Kriterien bestanden: AC-1/3/7/8/9/11/12 aus der Zielrunde unverändert, AC-2/4/5/10 durch diese Nacharbeit
geschlossen (jede mit einer Mutation, die vorher grün war und jetzt rot ist, plus je einer Schreibweise, die ich neu
erfunden habe), AC-6 als „vorbereitet, Grund gemessen, Lauf und Urteil beim Nutzer" — und diese Umschneidung ist durch
`DEC-0095` (6) gedeckt und im Protokoll benannt statt verschwiegen.

**Keine Runde 3.** Die sechs Punkte oben sind Redaktionszeilen bzw. Folgeitems; drei davon (1, 2, 3) kann der Lead
ohne Stempel und ohne Lauf erledigen, 4 und 6 sind Items für die nächste Runde, 5 ist nur eine Feststellung.

**Eigene Korrektur:** mein Zielrunden-Minimalfix für AC-4 ließ die ASCII-Umschrift `Pruefer` durch — ich hatte sie
als „Nebenbefund" notiert statt in den Fix gezogen. Die Nacharbeit hat sie geschlossen; `ac4c` ist jetzt rot.
