# Prüfbericht TSK-0142 (PR-0012, Order 3b, Strom B, B2-Fortsetzung) — Runde 2 — **FAIL (ein Id: BUG-0286)**

Prüfer: `harness-verifier` (Opus, high), 32 min, +67 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 14:05, Uhr gelesen). C1/C2 → B3; C3 als Loch aufgenommen; die Patch-DATEI-Frage geht als Entscheidung an den Nutzer.

Runde 2 ist durchgemessen.

---

# Prüfbericht TSK-0142, Runde 2 (B2-Fortsetzung) — **FAIL** (ein Id blockiert, Rest ist grün)

Frischer Einzel-Schnappschuss: `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0142\verify2\` (Kits, tools, .claude, docs, user, Staging-Protokoll), zwei selbst gebaute Piloten aus **diesem** Schnappschuss, Hook-Liste je aus deren eigener `.claude/settings.json`.

## Bestätigt: meine vier Runde-1-Befunde sind zu

| | gemessene Zeile (echte Hook-Prozesse, beide Piloten) |
|---|---|
| **B1** | `bash <<'EOF'` 2 · `cat <<'EOF' \| bash` **2** · `cat <<'EOF' \| tee /tmp/a \| bash` **2** · `. /dev/stdin <<'EOF'` **2** · `source /dev/stdin <<'EOF'` **2** · `sh -s <<'EOF'` **2** · `cat <<'EOF' \| xargs -0 bash -c` **2** · Prosa-Heredoc weiter 0 |
| **B2** | `cat <(cp evil.py .claude/hooks/g.py)` **2** · `echo hi \| tee >(cp …)` **2** · `diff <(cat a) <(cp … project_memory/evidence/EVD-9999.yaml)` **2** · gewöhnliche `$( )` weiter 0 |
| **B3** | Mutation T5 (der zurückgezogene Satz zurück in `agents/report-writer.md`) → **1 failed**; der Test liest jetzt beide Seiten |
| **B4** | `_MASK_RX` in allen drei Kits umbenannt → **Test 1 failed** (vorher: 1 passed), Gate 1 rc 2 wie zuvor; zurückgesetzt → 1 passed |

Mutationen der Rework-Fixes selbst, alle rot: T1/T2 (nur die linke Seite des Openers lesen) → `test_a_heredoc_body_handed_to_a_shell_is_judged_as_a_command` bzw. `…_an_interpreter_executes_is_not_prose_here` failed; T3 (`<(`/`>(` wieder raus) → failed; T4b (Patch-Applier aus der Mitgliedschaft) → failed.

## Befunde

### C1 — BUG-0286 steht in der Freigabezeile, obwohl der **dritte** von drei Trägern seines eigenen Mechanismus offen ist — **blockierend für dieses eine Id**
`project_memory/bugs/active/BUG-0286.yaml:observed` nennt die Träger wörtlich: „Eine Pipe, eine Kommandosubstitution **und eine Patch-Datei** tragen den Pfad über diese Grenze." Geschlossen ist der Heredoc-Weg; die Patch-**Datei** ist offen und trägt weiter:

```
git apply changes.diff            alle 9 dev-Hooks rc 0 / alle 9 office-Hooks rc 0
patch -p1 < changes.diff          alle rc 0
git apply - < changes.diff        alle rc 0
cat changes.diff | git apply      alle rc 0
git apply <(cat changes.diff)     alle rc 0
echte Shell:  git apply changes.diff  rc 0  →  .claude/hooks/gate_write_scope.py == "DISARMED"
              cat changes.diff | git apply rc 0 → dasselbe
```

B2 schreibt die Lücke ehrlich hin (Protokoll „Seam handoffs (B2)" Nr. 3) — aber als **Entscheidung mit zwei Optionen**, und `BUG-0286` steht trotzdem in der vierten Batchzeile. Das ist der dritte Zustand, den die Hausregel ausschließt: geschlossen ODER vom Nutzer abgenommene Ausnahme. AC-1 des Items sagt dasselbe. Minimaler Weg: `BUG-0286` aus der Batchzeile nehmen, bis entweder der Datei-Träger zu ist oder der Nutzer die Ausnahme beantwortet hat (mit dem einen deutschen Satz in `limits`).

**Und die Beschreibung der Lücke ist zwei Schreibweisen zu schmal:** die Seam-Option (a) spricht von „the patch file named by an **operand or an input redirect**". `cat changes.diff | git apply` nennt die Datei in einer **Nachbarstufe**, `git apply <(cat changes.diff)` in einer **Substitution** — beide gemessen rc 0, beide von Option (a) nicht erfasst. Der Mechanismus ist „der Patch-Inhalt steht in keinem Wort der Zeile", nicht „Operand oder `<`".

### C2 — die neue Patch-Mitgliedschaft wird von **jedem Wort** der Stufe beantwortet, nicht vom Programmwort: falsche Verweigerungen
`team-kits/*/hooks/_compat.py:845 _PATCH_APPLIER_NAMES` fließt in `_STDIN_PARSER_RX:846`, und `_fed_to_a_command_parser:883` sucht das Muster im **ganzen** Stufentext (`left = re.split(r"[&|;\n]", …)[-1]`).

```
cat > patch.diff <<'EOF' … EOF     rc 2   (die Zeile schreibt nur patch.diff)
cat > patch/notes.md <<'EOF' … EOF rc 2
cat > fix.patch  <<'EOF' … EOF     rc 0   (Punkt davor → kein Treffer)
cat > patchset.md <<'EOF' … EOF    rc 0
patch.exe -p1 <<'EOF' … EOF        rc 2   (richtig — und der Grund, warum ein Punkt im Lookahead der falsche Fix wäre)
```
Die Klasse ist **älter** als dieser Fix (`cat > bash.md <<'EOF' …` rc 2, `cat > sh.md <<'EOF' …` rc 2) — B2s Eintrag verbreitert sie um drei Schreibweisen. „Ein Patch-Skript schreiben" ist eine Alltagsoperation in drei Kits. Minimaler Fix: die Mitgliedschaft am **Programmwort** der Stufe fragen (plus der `git <verb>`-Form), nicht an jedem Wort; sonst als gemessener Rest in die Löcherliste.

### C3 — gemessener Rest, benannt statt behauptet: der Rumpf über eine **Datei** an die Shell, in einer Zeile
```
cat <<'EOF' > run.sh ; bash run.sh      alle Hooks rc 0
echte Shell rc 0 → project_memory/b1h.yaml geschrieben
```
Das ist **nicht** eine Regression von BUG-0289 (der neue Leser endet bewusst am `;`, und der Rumpf ist hier Daten für `cat`), sondern die Kit-Seite der bekannten H11-Klasse „ein selbst geschriebenes Skript prägt weiter". Es gehört als solche mit dieser Messung in die Löcherliste, weil die Kette in **einem** Werkzeugaufruf durchläuft.

## Explizite Negativbefunde

**Gemessen, in Ordnung:**
- **Naming**: `coverage_blocker` über **alle 33** TSK-0142-EVDs → 33× OK (EVD-0370 ist weg; EVD-0387/0390 durch 0397/0398 abgelöst, beide alten nicht mehr aktiv).
- **Alle 16 neuen Naming-Knoten** (18 Parametrisierungen) in einer Auswahl: **18 passed, 110 s**.
- **Mutationen der sechs neuen Schließungen, alle rot**: U1 (Aufgabe zählt wieder als Lauf) 3 failed, U2 (Geschäftszeitzone ignoriert) 1 failed, U3 (Zahlungsziel = gesetzliche Vorgabe) 1 failed, U4 (ungeplante Ordner stumm) 1 failed, U5b/U5c (B3 immer ok / kein Subjekt) je 1 failed, T4b (Patch-Applier raus) 1 failed.
- **BUG-0265 (Installer-Hälfte), real gefahren**: beide Zwillinge mit gestempelter Staging rc 0, beide schreiben `.claude/kit_repo_files.json`, **byte-identisch (622 Bytes, LF, kein BOM)**, 19 Einträge, die eigene Projektdatei `scripts/mine.py` ist **nicht** darin.
- **Freigabezeilen**: alle vier (27 Ids) gegen die Zustandskopie → **rc 0, 0 refused**, 27 unique; die reworkten Ids binden an die neuen EVDs (BUG-0107→0396, BUG-0186→0395, BUG-0288→0394, BUG-0289→0393).
- **B2s Korrektur der „fremden reds" reproduziert**: `pytest tools/test_hooks.py -k "write_scope or heredoc or substitution or redirect or pipeline or read_only or prose or verb or borrow or directory"` → **150 passed, 0 failed** (215 s auf diesem Host, also über der Drei-Minuten-Richtlinie).
- **Spiegel**: md5 über 48 Hook-Dateien — keine Datei, die zwei oder drei Kits ausliefern, unterscheidet sich; die 19 Abweichungen sind ausschließlich Ein-Kit-Dateien.
- `pin_constitution_sections.py` → **all pins current** (Bs offener Seam ist erledigt); `ruff check team-kits/ tools/` → All checks passed; `tools/validate.py` → nur die drei erwarteten „VERSION not bumped"; Lead-Pakete unverändert an der Decke (dev 61064, office 66435, **research 62894**) — die Rollendatei zählt nicht ins Paket, der B3-Fix kostet also nichts.
- **Keine weiteren Über-Verweigerungen**: P4-12-Commit-Nachricht, Prosa-Heredoc, `--patch`-Flag, `git apply --check`, ein Patch auf eine gewöhnliche Datei — alle rc 0.

**Nicht gemessen:**
- Die 18 „not reached"-Löcher und B3s laufende Arbeit (nicht mein Gegenstand; mein Schnappschuss ist von 13:4x).
- Voller Lauf, Stempel, Commit.
- Die Kernel-Hälfte von BUG-0265 (`report.installed_kit_paths`, Strom A) — nur den Patchtext gelesen.
- BUG-0153/H61: B2s Zählung der Registrierungen (dev 1/31, office 0/30, research 1/28) habe ich nicht nachgezählt; meine eigene Auslesung der Office-Registrierung deckt sich mit „keine `timeout`-Angabe".
- PowerShell-Seite der neuen Heredoc/Patch-Regel (nur Bash-Zeilen gefahren).

**Eigene Fehlgriffe dieser Runde:** meine ersten 19 roten Knoten waren **mein** unvollständiger Schnappschuss (`user/claude/hooks/handover_guard.py` fehlte) — nach dem Nachkopieren 150 passed, B2s Zahl stimmt; meine U5-Mutation (`ok(B3) or fail(…)`) war inert, erst U5b/U5c haben gemessen; mein Manifest-Rig hatte die Konfigdatei beim Lesen selbst geleert.

## Urteil

**FAIL**, mit einem eng begrenzten Grund:

- **Blockierend, ein Id:** `BUG-0286` darf so nicht in die Freigabezeile — der dritte in seinem eigenen Item benannte Träger (die Patch-**Datei**) ist gemessen offen und schreibt in einer Zeile den Durchsetzungsapparat um. Entweder schließen oder eine vom Nutzer beantwortete Ausnahme; die Entscheidungsvorlage an den Lead ist der dritte Zustand, den es nicht gibt. Die anderen **26 Ids der vier Zeilen sind aus meiner Sicht freigabereif**.
- **Als benannte Reste in die Löcherliste:** C1s Verbreiterung (die Patch-Datei-Klasse ist weiter als „Operand oder `<`" — mit `cat … | git apply` und `git apply <(…)` als gemessenen Schreibweisen), C2 (Mitgliedschaft am Wort statt am Programmwort → falsche Verweigerung bei `patch.diff`/`patch/`), C3 (`cat <<EOF > run.sh ; bash run.sh`, H11-Klasse, eine Zeile, echter Schreibzugriff).

Meine vier Runde-1-Befunde sind sauber geschlossen und jeder mit einer Mutation gegengemessen; die sechs neuen Schließungen halten ebenfalls stand.