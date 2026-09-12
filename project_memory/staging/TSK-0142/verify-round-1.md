# Prüfbericht TSK-0142 (PR-0012, Order 3b, Strom B, erste Hälfte: 21 Schließungen) — Runde 1 — **FAIL**

Prüfer: `harness-verifier` (Opus, high), 35 min, 246 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 12:46, Uhr gelesen). Nacharbeit an B2 (der laufende Bauer desselben Items; B ist beendet).

Alle Messungen sind gefahren; hier der Bericht.

---

# Prüfbericht TSK-0142 (Strom B, erste Hälfte) — **FAIL**

Arbeitskopie (read-only gegen das Repo, eigenes Rig, `cwd`-gebunden, binär lesend/schreibend):
`C:\Offline Repos\v2-testbed\_round-scratch\TSK-0142\verify\` — Rig unter `…\verify\_rig\`, zwei selbst gebaute Piloten (`_rig\pilot-dev`, `_rig\pilot-office`, Hooks/Settings/Kernel aus dem Schnappschuss; der echte Scaffold rollt wegen des fehlenden Stempels zurück — erwartet, kein Befund).

## Befunde

### B1 — `gate_write_scope` + `_compat`: ein Hier-Dokument, das die Shell über eine PIPE bekommt, ist weiter Prosa (BUG-0289/H205 nur in zwei Schreibweisen geschlossen) — **blockierend**
`team-kits/*/hooks/_compat.py:842 _fed_to_a_command_parser` (liest nur das Segment **vor** dem Opener) über `prose_heredoc_free:893`, benutzt in `team-kits/*/hooks/gate_write_scope.py:908 prose_removed_view`.

Gemessene Zeile (echte Hook-Prozesse, alle in `pilot-dev/.claude/settings.json` registrierten Bash-Hooks, plus echte Git-Bash als Schiedsrichter):

```
B1 bash <<'EOF' … EOF          g.write_scope=2   (die Zeile, die der Fix vorführt)
B2 cat <<'EOF' | bash          g.git=0 g.test_coverage=0 g.memory_complete=0 g.packaging_decision=0
                               g.pipeline=0 g.write_scope=0 g.push_token=0 g.shell_hygiene=0 g.test_scope=0
B5 . /dev/stdin <<'EOF'        alle 9 rc 0   (office: alle 7 rc 0)
bash -c: B2 rc 0, B5 rc 0  →  project_memory/b2.yaml, project_memory/b5.yaml geschrieben
```

BUG-0289 sagt selbst: „Der Mechanismus ist die **Spanne**, nicht eine Schreibweise: welches Verb davorsteht … spielt keine Rolle." Geschlossen sind `bash <<EOF`, `bash -s <<EOF`, `zsh <<EOF` (Parser **links** vom Opener); offen bleiben der Pipe- und der `. /dev/stdin`-Weg. Im Ledger-Gate trifft B2 ebenfalls zu (`cat <<'EOF' | bash` + `sed -i … ledger/2026.csv` → rc 0, während `bash <<'EOF'` rc 2 ist).
Minimaler Fix: in `_fed_to_a_command_parser` zusätzlich die Stufen **hinter** dem Opener derselben Pipeline lesen (`|`-Stufen bis zum nächsten `;`/`&&`/`||`/Newline) und `.`/`source` in `_EVAL_NAMES` aufnehmen; eine Zeile je Schreibweise in `test_a_heredoc_body_handed_to_a_shell_is_judged_as_a_command`.

### B2 — `gate_write_scope`: Prozess-Substitution ist ein Befehl in einem Wort und wird nicht gelesen (BUG-0288/H204) — **blockierend**
`team-kits/*/hooks/gate_write_scope.py:836 _SUBSTITUTIONS_BY_SHELL` kennt `$(`, Backtick, `@(` — nicht `<(` / `>(`.

```
A1 echo $(cp evil.py .claude/hooks/g.py)      write_scope rc 2
C1 cat <(cp evil.py .claude/hooks/g.py)       alle 9 dev-Hooks rc 0, alle 7 office-Hooks rc 0
C1s cat <(cp evil.yaml project_memory/evidence/EVD-9999.yaml)   alle rc 0
bash -c "cat <(cp src.txt project_memory/c1.txt)" rc 0 → project_memory/c1.txt geschrieben
```

Das Gegenbeispiel steht in derselben Runde eine Datei weiter: `team-kits/office-team/hooks/gate_ledger_valid.py:349 _SUBSTITUTION_OPEN_RX = r"\$\(|<\(|>\(|`"` — dort ist die Klasse vollständig, im Schreibrechte-Gate nicht (dort rc 2 für `cat <(sed -i … ledger/2026.csv)`).
Minimaler Fix: `"<(" : ")"`, `">(" : ")"` in den `Bash`-Eintrag von `_SUBSTITUTIONS_BY_SHELL`; Zeile in `test_a_command_a_substitution_introduces_is_judged_as_a_command`.

### B3 — BUG-0186/H94: der Satz ist in den Skill gewandert, die **immer geladene** Rollendefinition widerspricht ihm weiter
`team-kits/research-team/agents/report-writer.md:29`: „… so **today** you stage the rendered files under `staging/<task-id>/` and **report that gap** (constitution §0 write-lock)." — derselbe zurückgezogene Satz, dessen Entfernung der Skill in `skills/report-writer/SKILL.md:37` protokolliert.

Gemessen: `tools/test_role_contracts.py::test_the_report_writer_is_told_the_command_that_files_its_render` liest ausschließlich die SKILL-Datei (Mutation S1b „alle `freeze-report`-Nennungen aus dem Skill" → 1 failed; S1c „falscher Satz zurück in den Skill" → 1 failed; die Rollendatei wird nie gelesen). Die Rollendefinition ist injiziert, der Skill ist laut derselben Datei „REGISTERED, **not injected**" — der Satz steht also genau dort, wo die Rolle zuerst liest. `team-kits/research-team/**` liegt in `allowed_scope`.
Minimaler Fix: die Teilzeile in `report-writer.md:29` auf `freeze-report` umschreiben und die Assertion des Tests auf die Rollendatei ausdehnen.

### B4 — BUG-0107/H15: die erklärte Leihfläche deckt eines von **zwei** geliehenen Modulen
`team-kits/*/hooks/gate_write_scope.py:901 HARNESS_BORROWS` erklärt die privaten Namen dieses Moduls. Der Workshop leiht aber auch aus `_compat`: `.claude/hooks/_harness.py:1556 return bool(compat_module._MASK_RX.search(span))` — und `_compat.py` erklärt nichts.

```
Basis:                      gate_lead_write_scope,  "echo x > ~/notes.txt"  rc 0
_compat._MASK_RX umbenannt: gate_lead_write_scope                           rc 2 (fail-closed, Sitzung dicht)
tools/test_hooks.py::test_the_harness_borrows_only_what_this_kit_declares   1 passed
```

Das ist exakt die Ausfallart, die BUG-0107 beschreibt („ein Gate, das nicht ausführen kann, verweigert jeden Aufruf der Sitzung"), unbemerkt vom Stolperdraht. Fail-closed, also kein Durchlass — aber eine **gemessene, nirgends aufgeschriebene** Lücke. Minimaler Fix: `HARNESS_BORROWS` auch in `_compat.py`, und der Test liest zusätzlich die Attribute auf dem Empfänger `compat_module` (er filtert heute hart auf den Variablennamen `module`, `test_hooks.py:19481`) — oder Rest mit Messung in die Löcherliste.

## Explizite Negativbefunde

**Gemessen, in Ordnung:**
- Naming/DEC-0100: `naming_tests.coverage_blocker` über **alle 23** EVDs von TSK-0142 → 22× OK; einzig EVD-0370 („Knoten existiert nicht") — genau die von B als abgelöst gemeldete. Alle 21 geschlossenen BUGs haben je eine EVD, jede mit `artifact_ref staging/TSK-0142/protocol.md`.
- Die drei Batch-Zeilen gegen eine **Zustandskopie** (Kernel direkt): 3× rc 0, **0 refused**, 21 Ids, jede genau einmal; BUG-0186 wird an **EVD-0376** gebunden (nicht 0370). EVD-0376 nennt `related: BUG-0186` — **nicht** BUG-0263; EVD-0367 nennt BUG-0263 (C's Abschluss, coverage_blocker OK, nicht in den Batch-Zeilen).
- Alle **23 Naming-Knoten** in einer Auswahl in der Kopie: 24 passed/56,8 s (zwei Parametrisierungen erst rot, weil ich `docs/` noch nicht kopiert hatte; nach dem Nachkopieren 2 passed).
- **19 Mutationen rot** (je Mutant → Knoten): M1 heredoc wieder pauschal entfernt, M2 Substitutionskörper verworfen, M3b/M3c Verb aus `_DIRECTORY_VERBS` entfernt, M4 Leihname entfernt, M5/M5b `_syntax_view` = Klartext, M6 Substitutions-Opener mitgefüllt (BUG-0065-Rückfall), M7 `uses_an_unguarded_validator` stumm, M8 Decoy-Frage wieder im Schreibzweig, N1 `mir/mirror` raus, N2 Slash kein Flag, N3b Ledger leiht die alte Heredoc-Regel, N4b nur Backslash aufgelöst, P1 Steuerzeichen gepflanzt, P2 Renderer nicht gestartet, P3 Dublettenregel stumm, P4 `conformance.findings` ignoriert, Q1 vierte musterfreie Ausnahme, Q2 `light: haiku` zurück, R1 Recorder-Verweigerung entschärft, R2 Term gefüllt, S1b/S1c Skill, S2 Skip entfernt.
- **Über-Verweigerungen** (Gegenrichtung) keine: die vier zurückgenommenen Ledger-Über-Verweigerungen sind rc 0, die echten Angriffe weiter rc 2 (`… ledger_add.py --validate … && git commit` 2, `python tools/ledger_add.py` allein 2, `>>`/`sed -i`/Substitution 2, BUG-0065-`tar`-Zeile 2); 8 gewöhnliche Office-Zeilen und 6 gewöhnliche Dev-Zeilen alle rc 0.
- **Spiegel**: md5 über alle 48 Hook-Dateien der drei Kits — jede Datei, die mehr als ein Kit ausliefert, ist byte-identisch (`gate_write_scope.py` dev=office=research, `_compat.py` ebenso); die 19 Abweichungen sind ausschließlich Dateien, die nur ein bzw. zwei Kits ausliefern. Keine `KIT_SPECIFIC_HOOKS`-Verletzung.
- **Decke**: `lead_package.size` vs. `tools/lead_package_sizes.json` → dev 61064/61064, office 66435/66435, **research 62894/62894** — kein Wachstum, Bs Begründung für den Umzug des Satzes trifft zu; die drei Verfassungen sind gegen HEAD unverändert (`git diff --stat HEAD` leer).
- **H193**: PowerShell-eigener Parser über `scaffold_team.ps1`, `init_project_memory.ps1`, `install.ps1` → je `parse-errors=0`; der .ps1-Zwilling verweigert eine Staging ohne `write_kit_state.py` **vor** dem Kopieren (rc 1, Repo danach nur `project_memory`).
- **H117-Laufzeit**: PostToolUse-Ledger-Hook mit Render über 59 Zeilen → rc 2 in **0,6 s**, Seite geschrieben; `dashboards/ABOUT.txt` behauptet nichts Ungebautes (nennt 20-s-Grenze und „nur bei Tool-Aufrufen" ausdrücklich).
- `ruff check team-kits/ tools/` → All checks passed. `tools/test_office_package.py` → **73 passed/87 s** (Bs 21 reparierte Tests grün). `test_a_heredoc_body_is_prose` + `test_a_continuation_the_named_shell_does_not_honour_is_not_joined` → 25 passed. `pin_constitution_sections.py` → genau **1 CHANGED** (dev ENFORCEMENT.md §1), wie im Seam-Handoff beschrieben.

**Nicht gemessen (bewusst):**
- Die 23 „not reached"-Löcher und BUG-0056/Seam S3 (B2s Arbeit, nicht mein Gegenstand).
- Der volle Lauf, der Stempel, `bump_kit_version.py` (Lieferkriterium der Runde).
- `tools/test_model_ladder.py::test_no_shipped_kit_text_still_names_the_retired_user_gated_ladder` — in meiner Kopie rot, weil sie `git ls-files` braucht und die Kopie kein `.git` hat; die Textseite von BUG-0250 habe ich stattdessen über alle sieben genannten Dateien gelesen (keine `sonnet-xhigh`/`light: haiku`-Reste).
- `guard_fs_tripwire` jenseits der zwei Mutationen: keine breite Ablage-Probenmatrix gefahren.
- PowerShell-Seite von `gate_write_scope` nur mit vier Zeilen (`Set-Location`, `$( )`, `@( )`, `& { }` — alle rc 2).
- Die Seams an A und an den Nutzer-Patch (BUG-0139/H47, BUG-0055) nur gelesen, nicht nachgemessen.
- Registrierte `timeout`-Werte: die Kit-`settings/settings.json` nennt für **keinen** Eintrag ein `timeout` — liegt in `forbidden_scope` dieses Items, daher hier nur als Beobachtung, nicht als Befund gegen B.

**Eigene Fehlgriffe:** zwei meiner Mutationsläufe haben den Mutanten liegen lassen (einmal Prozessabbruch mit gepuffertem stdout, einmal ein Anker, der nicht traf) — beide Dateien habe ich von Hand zurückgesetzt und die Kopie danach per md5 gegen das Repo geprüft (8/8 identisch). Meine erste M3-Mutation („`_walk` fragt wieder wörtlich `popd`") war **inert** — `pop-location` ohne Argument fällt ohnehin in den `return None`-Zweig; der Stolperdraht ist über M3b/M3c belegt, mein Verdacht war falsch.

## Urteil

**FAIL.**

- **B1** und **B2** blockieren: die Angriffskette läuft innerhalb einer Sitzung durch, schreibt kanonischen Zustand bzw. den Durchsetzungsapparat, und kein registrierter Hook der beiden Piloten verweigert sie. Beide Löcher sind Schreibweisen **derselben Mechanismen**, die BUG-0289 und BUG-0288 in ihren eigenen Items als Spanne bzw. als Klasse („ein Befehl in einem Wort") beschreiben — die Schließung ist damit breiter behauptet, als sie gebaut ist. Entweder die Schreibweisen schließen (je ein Einzeiler plus Testzeile) oder die beiden Items behalten einen benannten, gemessenen Rest; die Verifikations-Batchzeile darf BUG-0288/BUG-0289 bis dahin nicht auf VERIFIED laufen.
- **B3** blockiert die Schließung von BUG-0186 (der zuerst gelesene Text weist die Rolle weiter zum zurückgezogenen Verhalten), in Scope, ein Satz.
- **B4** gehört als **benannter Rest in die Löcherliste** (fail-closed, kein Durchlass) — mit der gemessenen Zeile, nicht mit den zwei Schreibweisen, die ich zufällig probiert habe: der Mechanismus ist „der Workshop leiht private Namen aus **jedem** Kit-Modul, erklärt ist nur eines".

Die übrigen 18 Schließungen halten meiner Messung stand: Naming, Rot-Zuerst-Mutation, EVD-Knotenliste, Spiegel und Batchzeilen stimmen.