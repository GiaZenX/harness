# Prüfbericht TSK-0143 (PR-0012, Order 3b, Strom C) — Runde 1 — **FAIL**

Prüfer: `harness-verifier` (Opus, high), 36 min, 228 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 11:53, Uhr gelesen). Nacharbeit an Bauer C (DEC-0096: FAIL 1 → gleicher Bauer).

## Prüfbericht — TSK-0143 (Strom C, PR-0012 „Bug-Null", Auftrag 3b)

**Arbeitsweise:** Baumkopie einmalig nach `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0143\verify\tree` (2881 Dateien, ohne `.git`), eigenes Rig `…\verify\rig.py` (verweigert sich außerhalb des eigenen Verzeichnisses, liest/schreibt Bytes). Im Repo nur gelesen. Offenlegung nach `DEC-0095` (6): das Protokoll habe ich **ganz** gelesen (349 Zeilen in drei Schnitten) — das war die Kostenentscheidung, weil jede Zeile eine zu prüfende Behauptung trägt.

---

### Befunde

**F1 — blockierend. `.claude/hooks/test_gates.py:6084` (`_touches_the_clock`), zusammen mit `:6148` (`_name_bound_to_a_clock_reading`)**
Der Docstring behauptet eine **Definition**: „A DEFINITION AND NOT A LIST OF CLOCK FUNCTIONS: anything in `time` is about time, so a helper that reaches into that module at all…", und der Leser darüber verspricht „a test that starts timing something tomorrow is read without being added anywhere". Gebaut ist nur **eine Schreibweise**: `ast.Attribute` auf dem Namen `time`.
Gemessene Zeile (drei synthetische Quellen durch die drei Leser):

```
time.X                 spans=2 reported=['line 8: the span opened at line 7 calls `_size` …']
from time import       spans=0 reported=[]
import time as clock   spans=0 reported=[]
```

Und Ende-zu-Ende, Mutation `v2b_h161_both` = der H161-Defekt wiederhergestellt **plus** Messhelfer auf `from time import monotonic` umgestellt:
`python -B -m pytest .claude/hooks/test_gates.py -q -k no_timed_span_here` → **1 passed in 1.74 s** (grün), während derselbe Defekt in der Schreibweise `time.monotonic()` **1 failed in 2.46 s** ist.
Das ist genau die Klasse „Leser liest weniger, als sein Docstring behauptet". Minimalfix: die Uhrnamen aus den **Import-Anweisungen der Datei selbst** ableiten (`ast.Import`/`ast.ImportFrom` auf `time`) statt aus dem festen Präfix — in beiden Lesern je ~3 Zeilen; alternativ den Docstring auf die gebaute Schreibweise verengen.

**F2 — blockierend (falscher Kommentar). `.claude/hooks/test_gates.py:5548`**
`# (d), the sweep -- empty in this directory today, and it says so rather than implying a stand`.
Gemessen über `_said_in_the_hook_sources` + `_points_into_another_file`: **2** Querdatei-Zeiger, beide in `gate_test_scope.py`, beide auflösend. Der Docstring desselben Tests (`:5507-5510`) sagt es richtig; der Kommentar ist der Satz, den die Korrektur stehen ließ. Minimalfix: Teilsatz streichen.

**F3 — blockierend (Zeiger ins Leere). `tools/test_repo_hygiene.py:1241`**
Der Kommentar nennt `` `test_no_fence_blinds_the_pointer_sweep_for_the_rest_of_a_file` ``. Gemessen (`grep -rn` über den ganzen Baum, `--include=*.py --include=*.md`): **genau ein Treffer — das Zitat selbst**. Der Test heißt `test_no_pairing_shift_blinds_the_pointer_sweep_for_the_rest_of_a_file` (`:1247`). Zusätzlich behauptet der Satz eine „per-file half", die dieselbe Runde ausdrücklich **gegen** sich entschieden hat (AC-3, Docstring `:1264-1270`). Der Zeiger liegt exakt im Doppel-Blindfleck: der unqualifizierte Namensleser deckt nur `.claude/hooks/`, der Knoten-Id-Sweep nur `team-kits/` und `docs/` — also die Lücke, die diese Runde als H187/BUG-0270 herabgestuft hat. Minimalfix: Namen richtigstellen oder Satz streichen.

**F4 — blockierend (Zahl, die die Messung nicht trägt). `tools/test_repo_hygiene.py:1254`, `:1120`, `:1237` und EVD-0359**
Behauptet: „the judged corpus of this sweep goes from **150 to 654** over this tree" (wörtlich auch in EVD-0359: „Judged corpus 150 -> 654"). **150 war die alte Untergrenze des `assert`, kein Zählstand.** Gemessen, derselbe Korpus, HEAD-Leser gegen ausgelieferten Leser:

```
HEAD-Leser ueber DIESEN Baum: 617
judged (fence-aware):        672 in 172 files
```

Der Gewinn ist ~9 %, nicht Faktor 4,4. Dazu zwei Zahlen für eine Tatsache in einer Datei: Kommentar `:1237` sagt **642**, Docstring `:1254` sagt **654** (heute 672). Und `:1120` „contributed 0 of its 8 node ids" — gemessen für `docs/office-kit-from-field.md`: **alt 0, neu 14**. Minimalfix: eine Zahl an einer Stelle, oder gar keine; EVD-0359-Summary über den Kernel korrigieren, weil der Lead BUG-0263 auf diesem Satz schließt.

**F5 — Entscheidung des Leads/Nutzers, kein Codedefekt. BUG-0165 / H73**
Das Wort des Nutzers erlaubt Ausnahmen nur für Hersteller-/Plattform-/Welt-Grenzen. `docs/holes/H73.md` nennt (a) selbst „**die eine echte Lücke**" **mit Schließrichtung**, und die Schließrichtung landet in `tools/test_repo_hygiene.py` — im `allowed_scope` dieses Items. Der Umsetzer schreibt ehrlich „NOT ATTEMPTED in this round", stellt die Zeile aber in Batch REST-1, also in die Ausnahme-Frage. Das ist der dritte Zustand („bekannt, später") in der Form einer Ausnahme. (b)(c)(d) sind ehrlich begrenzt (ein Prosatest kann Verhalten nicht messen). Schwächere, aber gleiche Form: BUG-0102/H10 — Budget, keine Weltgrenze; der Satz benennt wenigstens Methode und Kosten. **Gehört zurück in die Arbeit oder vor eine ausdrücklich informierte Nutzerentscheidung.**

**F6 — Restposten. `project_memory/staging/TSK-0143/limits-update-lines.md:27`**
Zitiert `backlog_types.AUTOMATA["BUG"].terminal_from` als Autorität. Gemessen: `getattr(a, "terminal_from", None)` → `None` (der Parameter wird im Konstruktor zu `self.allowed` verrechnet). Die Sache selbst stimmt: `allowed nach ACCEPTED_EXCEPTION: [('TRIAGED', 'ACCEPTED_EXCEPTION')]`, Quelle `team-kits/kernel/backlog_types.py:87`. Minimalfix: Zeiger auf `.allowed` bzw. `backlog_types.py:87`.

**F7 — Restposten. `project_memory/staging/TSK-0143/h182-harness-patch-EXTENDED.md` (Prosa zu Stelle 6)**
„`.claude/hooks/test_gates.py:539` says so" — die Aussage steht heute in `:553-557`; „NOT to change … `test_gates.py:1812`" — die alte Messung steht heute in `:1902` (1812 ist der HEAD-Stand, den die +565 Zeilen dieser Runde verschoben haben). Die **Anker selbst** sind Text und lösen alle sauber auf (siehe negative Befunde), das Anwenden funktioniert; nur die Zeilenzeiger sind veraltet.

**F8 — Bemerkung. `project_memory/staging/TSK-0143/limits/*.json`**
Die 35 Sätze transliterieren Umlaute („Waechter", „vollstaendige"), obwohl der Nutzer sie in der Freigabefrage liest und der Kernel dort echte Umlaute ausgibt („Freigabe erbeten: … für diese 8 Fehler"). Kosmetisch, aber es ist die Fläche, die der Nutzer liest.

---

### Negative Befunde — **gemessen**

* **Benennung, 8/8:** eigenes Skript `…\verify\check_naming.py` über `kernel.naming_tests`: für EVD-0351/0353/0354/0355/0356/0357/0358/0359 je `blocker=''` und der benennende Knoten identifiziert (z. B. `EVD-0358 BUG-0008 nodes=5 naming=[…test_no_tool_trace_lies_unaccounted_for_in_the_repo_root] blocker=''`).
* **Rot-zuerst selbst nachgestellt:** H161 `1 failed in 2.46 s`; H45(b) `_can_arbitrate`-Vorform `1 failed in 4.20 s` (Subjekt ist der echte WSL-Starter `C:\WINDOWS\system32\bash.exe`, kein Stellvertreter, kein Skip); H206 Mint-Hälfte (`"PostToolUse"`-Schlüssel entfernt) `1 failed in 4.12 s`; H191 weite Lead-in-Verzweigung `1 failed in 2.10 s`; H181 `readable = text` `1 failed in 2.00 s`.
* **Zwei Angriffe in MEINER Richtung, nicht der des Umsetzers — beide halten:** H41 (a) eine auflösende, aber nicht deklarierte Zeiger-Schreibweise (`` `…;` ``) in `gate_test_scope.py` eingeschleust → `1 failed in 3.90 s` („writes a pointer as '%s;', which SPELLINGS_OF_A_POINTER does not declare"); H190 ein weiterer **fett** gesetzter Name im Bullet von `radar/README.md` → `1 failed in 4.03 s`.
* **Kein Rückschlag durch den Fence-Fix:** über den ganzen Korpus verliert **0 Dateien** ein Zitat durch das Ausblenden der Blöcke (Vergleich je Datei, alter vs. neuer Leser).
* **EVD-Läufe reproduzieren:** 7 Knoten `7 passed in 16.53 s`, 4 Knoten `4 passed in 4.86 s`; `test_every_test_pointer_this_repo_writes_resolves` grün in `114.74 s` auf meinem Schnappschuss (672 Zitate, alle auflösend).
* **BUG-0008:** mit Index in der Kopie `2 passed in 2.79 s` (ohne Index Skip — so gebaut); im echten Repo trägt `git status --porcelain` heute **keinen** unverfolgten Eintrag auf oberster Ebene, `Microsoft/` ist mit Begründung in `.gitignore:30-43`.
* **Liste (ii), selbst nachgebaut:** 35 `update`-Zeilen gegen eine Store-Kopie im Checkout → **0 verweigert**, kein leeres `limits`; sechs `hole_exception`-Batchzeilen je **rc 0**; 35 Ids, jede in genau einer Zeile. Der Jargon-Anspruch hält: kein „Shell/Hook/Gate/Client/Interpreter" in den 35 Sätzen.
* **OPEN/TRIAGED-Befund bestätigt, identische Menge:** 14 OPEN (BUG-0251, 0254, 0255, 0257, 0269, 0270, 0273, 0282, 0283, 0284, 0287, 0291, 0292, 0293), 21 TRIAGED; einzige Kante nach `ACCEPTED_EXCEPTION` ist `('TRIAGED','ACCEPTED_EXCEPTION')`.
* **Verifikations-Batch selbst neu gebaut:** `request-approval verification --batch BUG-0008 … BUG-0290` gegen `tree/store-copy` → **rc 0**, Frage mit allen acht Items und ihren EVDs, Prüfsumme `511bc75b60de…`.
* **Liste (iii) nachgezählt:** 121 Zeilen, 121 verschiedene `H`, **ja 95 / gesperrt 8 / nein 18** — genau die Korrektur des Umsetzers; der BEFORE-Anker kommt genau einmal vor.
* **Liste (i):** alle **sieben** Anker lösen **genau einmal** in der genannten Datei auf (Stelle 6 `_harness.py:1596`, Stelle 7 `settings.json:2`); die 12 Blöcke der TSK-0140-Datei stehen wortgleich in der erweiterten (Stellen 1–5 unverändert). Stelle 7 angewandt: JSON bleibt gültig, 8 Einträge, Kontrolllauf `-k "registration or gate_table or spawn"` **15 passed in 217 s**; Stelle 6 angewandt: `prose_is_one_that_exists or gate_table or pointer_reader_answers` **3 passed in 86,9 s**.
* **Registrierung gelesen statt erinnert:** 8 Einträge, jeder mit `"timeout": 120`; `PostToolUse/AskUserQuestion → gate_approval.py`; fünf Gate-Skripte aus `.claude/hooks/`.
* **H207-Schranke unabhängig gegengelesen:** `SR-0006` steht allein nur in `.claude/settings.json:2`; `CLAUDE.md:180`, `docs/holes/H2.md`, `docs/holes/H7.md` nennen die Ablösung.
* **Naht BUG-0032 zu Recht abgegeben:** die Waisen-Heuristik steht in `team-kits/kernel/report.py:669-681`; `tools/validate.py` (388 Zeilen) trägt nichts davon.
* **Disziplin:** kein Commit (HEAD unverändert `10a5127`), kein Stempel, keine Prägung — alle 11 offenen Anfragen im echten Store sind `created: 2026-09-12T09:15:4x`, also vor der Existenz von TSK-0143 (09:49); C hat acht EVDs (11:03–11:04) geschrieben. `ruff check` über die fünf geänderten `.py`: **All checks passed**.

### Negative Befunde — **nicht gemessen**

* Die Probe `probe_contracts.py` (H207: 0/0/4/1) habe ich nicht nachgefahren, nur über `SR-0006` gegengeprüft.
* Den 5-Knoten-Hygiene-Lauf nicht als **eine** Zeile (3 Knoten + den 114-s-Sweep einzeln).
* Die Schranken von BUG-0102/H10, BUG-0177/H85, BUG-0206/H122, BUG-0234/H152, BUG-0270/H187, BUG-0241/H159, BUG-0166/H74 gelesen, nicht nachgemessen (bei H74 habe ich das Messdokument geprüft: es behauptet den Faktor 11 **nicht** als gültig, sondern führt ihn samt Kritik — kein Befund).
* Kein Volllauf; `tools/test_hooks.py`, `tools/test_hooks_v2.py`, `tools/test_pointer_sweep.py` nicht gefahren — der gemeldete fremde Rote (`scaffold_team.ps1:545`, Strom B) ist von mir **nicht** bestätigt.
* Mein Schnappschuss ist von ~11:20; spätere Schreibvorgänge von A/B sehe ich nicht.

**Eigener Fehlschlag, offen gesagt:** meine Hypothese, `test_the_session_guards_watch_list_is_built_without_a_shell` messe nur „benutzt `_posix_shells` nicht" statt „benutzt keine Shell", ließ sich **nicht** belegen — die Mutation mit fest verdrahteter `bash`-Zeile ging rot (`ERROR .claude\hooks\test_gates.py:179`), wenn auch aus einem anderen Grund (die Zeile erzeugte die Datei nicht). Kein Befund gegen H45(a).

---

## Urteil: **FAIL**

Die Substanz ist stark: alle acht Schließungen sind echt, benennen ihren Bug so, wie `kernel/naming_tests.py` liest, und werden unter meinen eigenen Mutationen rot; alle drei Listen bauen sich bei mir unabhängig nach.

**Blockierend für die Runde** (je wenige Zeilen, keine neue Messrunde nötig): **F1** (neuer Leser liest weniger als sein Docstring — unter der vom Docstring verneinten Mutation **grün**), **F2**, **F3**, **F4** (die 150→654-Behauptung steht auch in EVD-0359, dem Datensatz, auf dem der Lead BUG-0263 schließt — dort über den Kernel mitkorrigieren).

**Als benannte Restposten in die Löcherliste bzw. an den Lead:** **F5** (BUG-0165/H73 ist keine Hersteller-/Welt-Grenze; der Mechanismus ist „eine Ausnahme für eine Lücke, die der eigene Eintrag als hier schließbar führt" — nicht die zwei Schreibweisen, die ich geprüft habe), **F6**, **F7**, **F8**.

Relevante Pfade: `C:\Offline Repos\AgentAndSkills\.claude\hooks\test_gates.py`, `C:\Offline Repos\AgentAndSkills\tools\test_repo_hygiene.py`, `C:\Offline Repos\AgentAndSkills\project_memory\staging\TSK-0143\` (Protokoll und die drei Listen), mein Prüfstand `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0143\verify\` (`rig.py`, `check_naming.py`, `dry_check_lists.py`, `tree\`).