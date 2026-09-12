# Prüfbericht TSK-0143 (PR-0012, Order 3b, Strom C) — Runde 2 — **FAIL (ein Satz: R1)**

Prüfer: `harness-verifier` (Opus, high), 13 min, +70 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 12:31, Uhr gelesen). R2 an den Lead: die 14 TRIAGED-Transitionen sind laut Messung nicht nötig.

## Prüfbericht Runde 2 — TSK-0143 (Strom C), Nacharbeit zu F1–F8

Neuer Schnappschuss `…\verify\tree2` (2896 Dateien, ohne `.git`), eigenes Rig `…\verify\rig2.py` (verweigert sich außerhalb seines Verzeichnisses, Byte-Modus). Im Repo nur gelesen. Vom Protokoll habe ich **nur** den Abschnitt „Rework 1" gelesen (Zeilen 353–543).

### Nachgearbeitet und bestätigt

**F1 — geschlossen, beide Hälften.** `.claude/hooks/test_gates.py:6087` (`_clock_names`) leitet die Namen aus den Import-Anweisungen der Quelle ab; `_reads_the_clock` (`:6112`) wird von allen drei Lesern **und** von `_statement_that_closes_the_span` (`:6202`) benutzt — die dritte Stelle, die mein Befund nicht genannt hatte. Meine eigenen Mutationen gegen den neuen Stand:

* `v2b_h161_both` (Defekt + Helfer auf `from time import monotonic`) → **1 failed in 1.06 s**, `line 6066: the span opened at line 6065 calls _a_line_too_long_to_read_in, which reads the clock itself` — in Runde 1 war genau das **1 passed**.
* `v3_h161_alias` (Defekt + Helfer auf `import time as clock` **und** `perf_counter`, also zusätzlich eine dritte Uhrfunktion) → **1 failed in 1.09 s**.
* Span-Erkennung selbst, drei Quellen durch die Leser: `time.X spans=2`, `from time import spans=2`, `import time as clock spans=2`, jede mit Meldung (Runde 1: 2 / 0 / 0).

**F2/F3 — gestrichen.** `test_gates.py:5548` lautet jetzt `# (d), the sweep over this directory's own prose`; „empty in this directory today" kommt im Baum nicht mehr vor. `test_no_fence_blinds_…` findet sich nur noch in Protokoll- und Berichtsprosa; der Bodenkommentar `tools/test_repo_hygiene.py:1347-1351` nennt `test_no_pairing_shift_blinds_…`, und der existiert (`:1357`).

**F4 — Zahl steht einmal und ist reproduzierbar.** Einziger Ort ist der Docstring `tools/test_repo_hygiene.py:1361-1368`. Selbst nachgemessen auf meinem 20 Minuten jüngeren Schnappschuss: `alter Leser: 631 | neuer Leser: 686 in 172 Dateien | Dateien mit geaenderter Zahl: 15 | Dateien, die verlieren: 0` gegen seine 625/680/172/15/0. Der Betrag wandert (drei Ströme schreiben), die **Form** — 172 Dateien, 15 gewinnen, 0 verlieren — reproduziert exakt, und genau das behauptet der Docstring. Die alte 4,4-fach-Behauptung ist weg.

**F5 — H73/BUG-0165 ist wirklich gebaut, H10 ist ehrlich gebunden.** Der neue Test benennt den Bug (`coverage_blocker` leer, `naming=[…test_a_decision_named_in_a_message_a_user_reads_is_one_that_resolves]`). Eigene Pflanzung an **anderer** Stelle als der Umsetzer: tote Id in der echten Verweigerung `team-kits/kernel/cli.py:537` → **1 failed in 2.18 s**, `cli.py:537 DEC-9142 (in a message this program hands out)`. Docstring-Ausnahme wie behauptet: eine Id in einem Docstring wird nicht gemeldet. Korpus 69 Nachrichten-Zitate — selbst nachgezählt, exakt 69. H10s Satz nennt die **Entscheidung**, den Preis (405 Stellen, 553 Tests) und fragt den Nutzer; die 405 habe ich mit einer schlichten `ast`-Zählung (`If/While/IfExp/BoolOp`) über dieselben sieben Dateien auf **403** nachgerechnet — dieselbe Größenordnung, dieselbe Verteilung. Ehrlich gebunden.

**F6/F7/F8 — erledigt.** 34 Bodies (`bug-0165-limits.json` weg), **0 refused**, kein leeres `limits`; sechs Ausnahme-Batches rc 0, 34 eindeutige Ids, BUG-0165 in keinem; UTF-8-Umlaute in 33 von 34 Dateien, `bug-0198` ohne — dessen Satz trägt tatsächlich kein umlautpflichtiges Wort. Die neue **9-Id-Verifikationszeile** gegen eine Store-Kopie neben dem `tools/`-Baum: **rc 0**, alle neun in der Frage, `EVD-0378` genannt, `EVD-0359` **nicht**, `EVD-0377` für BUG-0165. Alle sieben Patch-Anker lösen weiterhin **genau einmal** auf; die Zeilenzeiger stimmen jetzt (`test_gates.py:556` liegt in `:554-561`, das alte Maß in `:1902`).

**H138 und der Pin.** `docs/holes/H138.md:22` zitiert `tools/test_design_conformance.py::test_a_draft_with_conformance_findings_is_refused_and_an_undecided_one_is_not` — vorhanden in `:187`; der alte Name steht nur noch in Staging-Protokollen, nicht mehr unter `docs/`. Die alte Kette ist ausdrücklich als „was VORHER galt" markiert. `python -B tools/pin_constitution_sections.py` → **3 kits, 12 files, 125 sections, all pins current** (1,53 s). `test_every_test_pointer_this_repo_writes_resolves` → **1 passed in 69,84 s** (der fremde Rote der Runde 1 ist weg). Neun EVDs, alle `blocker=''`. Keine Transition durch C (BUG-0165 `TRIAGED`, BUG-0263 `OPEN`), kein Commit (HEAD `10a5127`), keine neue Anfrage im echten Store (weiter 11, alle 09:15).

---

### Neue Befunde

**R1 — blockierend. `tools/test_repo_hygiene.py`, Docstring des neuen Tests (Absatz „WHY IT WAS UNJUDGED", die Aufzählung „sixteen … three handover-marker literals … and this is it") und EVD-0377 („H73 (a) CLOSED")**
Der Leser ist `ast`-basiert und die Sweep-Schleife ruft ihn nur `if rel.endswith(".py")`. Von den **16** Stellen, die `docs/holes/H73.md` (a) aufzählt, liegen **zwei** in Shell-Skripten (`scaffold_team.sh`/`.ps1`, die Handover-Marker-Literale) — die bleiben ungeprüft.
Gemessene Zeile: tote Id in das echte Marker-Literal `team-kits/scaffold_team.sh:284` gepflanzt (die Zeile, die das Skript nach `.claude/` schreibt) → `pytest tools/test_repo_hygiene.py -q -k "every_decision_pointer_in_a_shipped or decision_named_in_a_message"` → **2 passed in 2.87 s**, also **grün**. Zusatzmessung: der Prosa-Leser sieht sie auch nicht — `_dec_citations` auf die Markerzeile allein → `[]` (die Id steht in einem `"…"`-Span, genau der Mechanismus von H73 (a)).
Damit ist H73 (a) für die Python-Klasse geschlossen (14 der 16) und für zwei vom Eintrag ausdrücklich gezählte Stellen nicht, während Docstring und EVD „CLOSED" sagen. Minimalfix (eine Zeile, kein neuer Leser): im Docstring und in `docs/holes/H73.md` schreiben, dass die beiden Shell-Literale ungelesen bleiben, mit dieser Messung — oder BUG-0165 aus der Verifikationszeile nehmen. Das echte Lesen von Shell-/PS1-Literalen ist eine andere Definition und damit eigene Arbeit.

**R2 — Restposten, für den Lead handlungsrelevant. `project_memory/staging/TSK-0143/limits-update-lines.md`, Abschnitt „BEFORE THE BATCHES"**
Der Satz „each of those fourteen needs a `transition <id> TRIAGED` before its batch is asked, or the user's click lands on a refusal" wird von dem Leser, den er zitiert, nicht getragen. Gemessen gegen die Store-Kopie: `batch_walk_blockers(state, "hole_exception", ["BUG-0257","BUG-0273"]) -> []`, ebenso `["BUG-0102"]`, ebenso `verification` mit `["BUG-0263","BUG-0290"]`. Die Regel dieser Funktion ist „Status **weiter** als die Quelle der Kante", und `OPEN` liegt **davor**; dieselbe Funktion fragt `mint`, bevor es schreibt (ihr eigener Docstring). Keine Statuspflicht steht dazwischen: `STATUS_DEPENDENT_FIELDS` bindet `limits` erst in `ACCEPTED_EXCEPTION` (`backlog_types.py:639-642`).
Ehrliche Schranke meiner Messung: eine echte Prägung braucht den Klick des Nutzers — ich habe den Wächter gemessen, nicht den Klick. Folge, wenn der Lead dem Satz folgt: 14 Zustandsschreibungen, die niemand braucht.

**R3 — Restposten. EVD-0378**
Es trägt **nicht** dieselben Knoten wie EVD-0359: `tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves` — der Knoten, dessen Sweep die im Summary zitierten 625/680 überhaupt erzeugt — ist herausgefallen, dafür sind drei DEC-Zeiger-Knoten dazugekommen. Der Abschluss bleibt gültig (`blocker=''` über `test_no_pairing_shift_blinds_…`), aber der Datensatz zitiert eine Zahl aus einem Lauf, den er nicht aufzeichnet. Minimalfix: den Knoten in die `run_command` aufnehmen (er stand in EVD-0359) oder im Summary sagen, dass die Zahl aus der Sonde stammt.

**R4 — gemessener Restposten, kein Fehler.** Eine DEC-Id in einem **Docstring** einer ausgelieferten Kit-Datei wird von **keinem** der beiden Leser beurteilt (Nachrichten-Leser `[]` per Definition, `_dec_citations` `[]`, weil das Dreifach-Anführungszeichen länger ist als die Id). Der Code sagt die Ausnahme ausdrücklich, behauptet also nichts Falsches — aber die Stelle ist nirgends als Loch benannt.

### Nicht gemessen

Kein Volllauf; `tools/test_hooks.py`, `test_hooks_v2.py`, `test_pointer_sweep.py` weiterhin nicht gefahren (der PowerShell-Parserfehler in `scaffold_team.ps1:545` bleibt unbestätigt und ist Strom B). Die zwei git-gestützten Hygiene-Knoten liefen in `tree2` als Skip (kein Index) — in Runde 1 habe ich sie mit Index grün gemessen. Kein echter Mint. Streams A/B schreiben weiter; mein Schnappschuss ist von ~12:2x.

---

## Urteil: **FAIL** — ein einziger, eng begrenzter Punkt

**Blockierend: R1**, und zwar als Satz, nicht als Bauarbeit: eine Behauptung „geschlossen", die zwei vom eigenen Eintrag gezählte Stellen einschließt, welche unter einer Pflanzung nachweislich grün bleiben. Eine Zeile im Docstring, eine in `docs/holes/H73.md` — oder BUG-0165 raus aus der Verifikationszeile.

**Als benannte Restposten an den Lead: R2** (bitte die 14 Transitionen **nicht** blind fahren — die Messung sagt, sie sind nicht nötig), **R3**, **R4**.

Alles andere aus Runde 1 — F1, F2, F3, F4, F5 (H10), F6, F7, F8 — ist gearbeitet und von mir unabhängig nachgemessen; die zwei Zusatzaufträge (H138-Reparatur, Pin mit 125 Abschnitten) sind bestätigt.

Pfade: `C:\Offline Repos\AgentAndSkills\.claude\hooks\test_gates.py`, `C:\Offline Repos\AgentAndSkills\tools\test_repo_hygiene.py`, `C:\Offline Repos\AgentAndSkills\docs\holes\H73.md`, `C:\Offline Repos\AgentAndSkills\project_memory\staging\TSK-0143\limits-update-lines.md`, mein Prüfstand `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0143\verify\` (`rig2.py`, `check_naming2.py`, `dry_check_lists2.py`, `tree2\`).