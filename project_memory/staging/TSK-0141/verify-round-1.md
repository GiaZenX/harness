# Prüfbericht TSK-0141 (PR-0012, Order 3b, Strom A Kernel) — Runde 1 — **FAIL**

Prüfer: `harness-verifier` (Opus, high), 19 min, 178 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 11:52, Uhr gelesen). Nacharbeit an Bauer A (DEC-0096: FAIL 1 → gleicher Bauer, Aufwand hoch); B9 → Strom B.

## Prüfbericht — TSK-0141 (Strom A, Kernel), PR-0012 „Bug-Null", Order 3b

Arbeitskopie: `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0141\verify\tree` (2888 Dateien, binär gespiegelt durch `…\verify\mirror.py`, das sich außerhalb seines eigenen Verzeichnisses verweigert). Am Repo selbst nur gelesen. Gelesene Protokollabschnitte: Zeilen 18–155, 206–352, 494–700, 747–819 — **nicht** 155–206, 352–494, 700–747; das ist mein unbeleuchteter Rest.

---

## BEFUNDE

### B1 — H194/BUG-0278: die deutsche Verneinung ist weiter eine Aufzählung, und sie fehlt in der GEFÄHRLICHEN Richtung (blockiert die Schließung von BUG-0278)

`team-kits/kernel/dispatch.py:2896` — `_DENIES_RX` führt englisch `no|not|never|none`, deutsch aber nur `kein\w*|nicht`. Die Zwillinge von `never`/`none` (`niemals`, `nirgends`) fehlen.

Gemessene Zeile (Mutation des benennenden Tests in meiner Kopie, `mutate.py` + `tools/test_ladder.py`):

```
E   assert True is False
E    +  where True = reads('Ein Test wird niemals rot')
FAILED tools/test_ladder.py::test_a_german_acceptance_line_is_read_like_its_english_twin
1 failed in 2.26s
```

Direkt gegen den laufenden Leser (`probe_dispatch.py`): `_sentence_names_a_test("Ein Test wird niemals rot") = True`, `("Ein Test wird nirgends rot") = True` — ein Satz, der einen Test VERNEINT, wird als testförmige Abnahme gelesen und **gewährt die billige Sprosse**. Der Modulkommentar `dispatch.py:2863` sagt ausdrücklich, dieser Leser falle absichtlich in die andere Richtung („REFUSES the ask and leaves the order on the more expensive default").

Dazu Hausregel 3: `tools/test_ladder.py:489` behauptet im Docstring des benennenden Tests „**every clausal negation stays a refusal**" — eine Eigenschaft, die der Code nicht baut, in einem Test, der genau diese Eigenschaft tragen soll.

Minimalfix: `_DENIES_RX` um die deutschen klausalen Verneiner erweitern (`nie(mals)?`, `nirgend\w*`) **und** die Aufzählung an beiden Enden verdrahten wie `_VERDICT_WORDS` es schon ist (`test_the_acceptance_reader_needs_a_verdict_word_and_every_listed_one_earns_its_place` ist die Vorlage); die beiden Sätze als Reihen in den benennenden Test.

### B2 — derselbe Fix erzeugt eine NEUE Falsch-Verweigerung im Englischen (gehört zu B1)

`team-kits/kernel/dispatch.py:2898/2950` — `_denies_a_test` liest das Komplement einer Präposition „bis zum Satzzeichen". Im Vorfeld (deutsche Verbzweitstellung, englische Fronting-Form) verschluckt das den ganzen Hauptsatz.

Gemessen (`probe_before_after.py`, HEAD-Regeln rekonstruiert gegen den neuen Leser):

```
NACHHER:  False | Ohne den Fix wird ein Test rot.      False | Without the fix a test goes red.
VORHER :  False | Ohne den Fix wird ein Test rot.      True  | Without the fix a test goes red.
```

Der englische Satz war vor dieser Runde eine Zusage und ist es jetzt nicht mehr — die Symmetrie wurde hergestellt, indem Englisch genauso falsch wurde wie Deutsch. Richtung: Über-Verweigerung (teure Sprosse), also nicht blockierend, aber es ist ein Rückschritt, den die Runde eingebaut hat.

### B3 — H135/BUG-0218: der Kopfkommentar behauptet die Lücke, die der Fix geschlossen hat; die REAL verbliebene Klasse steht nirgends

`team-kits/kernel/scopes.py:31-34` sagt weiter: „the witness of `a/*x` does not match `a/y*` although `a/yx` lies in both, so a pair … passes here (`H135`)". Gemessen ist das Gegenteil: `pair_witnesses` liefert `a/yx`, der Knoten ist grün, und ich habe beide Rot-zuerst-Mutationen selbst nachgefahren:

```
m1 (pair_witnesses aus `overlaps` entfernt) -> AssertionError: [] / assert (0 == 1), 1 failed in 7.53s
m2 (Separator-Regel in _one_character deaktiviert) -> 1 failed in 2.17s
```

Zugleich ist die Vollständigkeitsbehauptung von `pair_witnesses` (`scopes.py:286`: „what the two orders COULD share") zu breit. Brute-Force gegen das AUSGELIEFERTE Prädikat (`probe_scopes.py`, alle Pfade bis Länge 5 über `abcxy/.`) findet **6 Paare mit echtem gemeinsamem Pfad und ohne jeden Zeugen**:

```
MISS  'a/b' x 'a/**/c'    real z.B. a/b/c   universe=['a/b', 'a/_/c']
MISS  'a/b' x 'a/*/c'     real z.B. a/b/c
MISS  'a/b' x 'a/**/*.py' real z.B. a/b/x.py
MISS  'a/b' x '**/c'      real z.B. a/b/c
MISS  'a'   x '**/c'      real z.B. a/c
MISS  'a'   x '*/c'       real z.B. a/c
```

Mechanismus (nicht die zwei Schreibweisen): `_unify` liest einen Eintrag **ohne Wildcard** als Literalpfad, während das Gate ihn als **Verzeichnis-Präfix** liest (er besitzt alles darunter). Jede Paarung „globfreier Eintrag × Glob-Eintrag" ist damit über einem leeren Baum blind.

Für den Live-Schnitt ist das folgenlos, und das habe ich gemessen: keine der drei Order trägt einen globfreien Verzeichniseintrag, und `check-scopes --only TSK-0141 TSK-0142 TSK-0143` in meiner Kopie (0 Dateien im Baum, also reine Zeugenhälfte) sagt `disjoint`, rc 0.

Minimalfix: den Kopfabsatz auf die tatsächlich verbliebene Klasse umschreiben (Hausregel 3, alarmierende Richtung) und die Präfix-Klasse als benannten Rest in die Löcherliste; der Bau selbst ist ein Einzeiler in `_tokens`/`_unify` (ein globfreier Eintrag bekommt ein implizites `/**`), gehört aber in eine eigene Runde mit Rot-zuerst.

### B4 — H81/BUG-0173: die zweite Fassung derselben Behauptung ist stehen geblieben

`team-kits/kernel/approvals.py:2101-2105` behauptet weiter: „`approval_mint_is_wired` records two measured directions, and one of them prints this sentence at a project that CAN mint — a registration whose command line it cannot decompose, the reachable shape being a quoted absolute path with a space in it. `H81` carries that".

Gemessen gegen den laufenden Code (`probe_report.py`):
`_invoked_scripts('python -B "C:/Offline Repos/p/.claude/hooks/_gate.py" "a b/gate_approval.py"') = ['_gate.py', 'gate_approval.py']` — genau diese Form zerlegt jetzt. Der Umsetzer hat den Absatz in `report.py` ersetzt und den in `approvals.py` übersehen; beide Dateien gehören diesem Strom.

### B5 — BUG-0271 „NOTHING remains" stimmt nicht (niedrig, aber die Behauptung ist der Defekt)

`project_memory/staging/TSK-0141/protocol.md:313-333`. Gemessen auf der echten Kommandofläche gegen eine Store-Kopie:

```
"question": "Freigabe erbeten: Abschluss behobener Fehler für diese 1 Fehler, jeder mit dem Testlauf, der ihn misst …"
"description": "… für 1 gemessen behobene Fehler: BUG-0032 (EVD-0369) …"
```

und über alle 15 Arten (`probe_question.py`): `hole_exception` fragt nach dem ITEM („… für ‚Kasse mit Bon' (PR-0001)"), während die freigebende Option etwas anderes bindet („für 1 Lücken bleiben offen: x-holes") — Frage und Karte benennen bei dieser Art nicht denselben Gegenstand, und die Singularform ist in beiden Arten falsch. Das ist genau die Fläche, um die BUG-0271 geht (der Satz, den ein Nicht-Entwickler beantwortet). Der benennende Test prüft Anfang, Enum-Wörter, Hash und Pfad — Numerus und Frage/Karte-Deckung nicht.

### B6 — H106/BUG-0190: das Kostenargument hält nicht, der Rest ist in diesem Repo baubar

`protocol.md:551-556` begründet die Nicht-Schließung mit der Unveränderlichkeit des `EVD` („a COUNT would have to be written after the fact"). Gemessen: die Umfangshälfte ist längst gebaut — jedes neue EVD trägt `run_scope:` (z. B. `EVD-0341: run_scope: selection`) —, und eine ZAHL muss auf keinem Datensatz stehen: sie ist eine Ableitung über die vorhandenen unveränderlichen Datensätze, genau wie jede andere Rollup in diesem Kernel. Der Leser dafür (`report.validate_state` / der Sitzungs-Brief) liegt in `team-kits/kernel/**`, also im Bereich dieses Stroms. Das ist in-repo-Arbeit, kein Welt-Limit — nach dem Wort des Nutzers geht die Reihe zurück in die Arbeit oder sie braucht seine ausdrückliche Ausnahme.

### B7 — Gruppe D („a measured design … no defect found to fix") trägt zwei Reihen, die dort nicht hingehören

`protocol.md:604-638`. **H171/BUG-0253**: das Item selbst sagt in AC-1 „a DEC decides …" — das ist keine fehlende Fehlerstelle, sondern eine ausstehende Entscheidung; unter einer Überschrift „kein Defekt gefunden" liest der Nutzer, es sei nichts offen. **H60/BUG-0152**: „ein nicht begangenes Interview hinterlässt eine leere Liste, die aussieht wie ‚nichts zu melden'" ist der Drei-Antworten-Fall, den dieser Kernel überall sonst baut (`kitupdate.pending_entries` hat in derselben Runde genau diese dritte Antwort bekommen: nicht gelesen ≠ leer). Ein Versuch ist nicht protokolliert.

### B8 — Zählfehler im Protokoll (trivial, aber der Lead legt die Zahl ab)

`protocol.md:802-819`: „nicht geschlossen: 21 — drei davon … (H183, H108, and H197's consumer)". Ausgezählt sind es mit H197 22 Nennungen, weil H197 zugleich unter den 23 geschlossenen steht. Die 21 stimmen nur, wenn der H197-Konsument nicht als eigene Reihe zählt.

### B9 — fremder Strom, gemessen, gehört zum Lead: EVD-0367 schließt BUG-0263 mit einem Knoten, der ihn nicht nennt

Nicht Strom A (artifact_ref `staging/TSK-0142/protocol.md`), aber ich habe es beim Prüfen aller 49 neuen EVDs getroffen. Gemessen mit dem Prüfer, den `approvals` selbst benutzt (`naming_tests.coverage_blocker`):

```
XX EVD-0367.yaml BUG-0263: its evidence names tools/test_office_package.py::test_every_test_the_field_report_verdicts_name_is_one_that_exists,
   and none of those tests NAMES BUG-0263 … (DEC-0100 (3), H195)
```

Fail-closed (eine Batch-Zeile darüber würde verweigert), aber die EVD steht mit `result: pass` im Store.

---

## NEGATIVE BEFUNDE — GEMESSEN

* **Die drei Verifikations-Batchzeilen**: alle drei selbst gegen eine Store-Kopie neben einem `tools/`-Baum gefahren, `rc2=0`, `rc3=0`, Zeile 1 rc 0 — **0 verweigert**, 22 Ids, jede in genau einer Zeile, keine Dublette. BUG-0242 ist in keiner (EVD-0361 ist `result: blocked`, kein Pass-Anspruch) — korrekt.
* **Die EVD-Knotenlisten**: alle 22 Stream-A-EVDs durch `naming_tests.coverage_blocker` — bis auf die beiden oben genannten (0361 blockiert, 0367 fremd) nennt jeder protokollierte Knoten seinen Bug so, wie `kernel/naming_tests.py` es liest.
* **Rot-zuerst nachgefahren**: H135 beide Mutationen (7,53 s / 2,17 s), B1 als eigene Mutation. Reverts sauber: `tools/test_parallel_scopes.py tools/test_backlog_types.py` → **70 passed in 34,64 s** (deckt sich mit 18 + 52 des Protokolls).
* **Der Live-Schnitt**: `check-scopes --only TSK-0141 TSK-0142 TSK-0143` → `disjoint`, rc 0; die drei `allowed_scope` tragen keinen globfreien Verzeichniseintrag, die Präfix-Klasse aus B3 trifft diesen Schnitt also nicht.
* **Scope-Treue**: die in `git status` geänderten Dateien von Strom A liegen sämtlich in `allowed_scope`; kein Übergriff.
* **S1/S3 liegen wirklich außerhalb** (`.claude/**` bzw. `team-kits/*.sh|*.ps1` stehen in `forbidden_scope`). **S2 nur zur Hälfte**: die Kernel-Seite (`team-kits/kernel/cli.py`) gehört Strom A; das Argument „eine Hälfte allein macht `tools/test_hooks.py::test_every_evidence_command_…` für alle rot" trägt, aber S2 ist damit **in-repo-Arbeit der Runde**, keine Nutzer-Ausnahme.
* **Kernhälfte von S1 konsistent**: `backlog_types.is_finished` ist additiv, hat im Kernel keinen Konsumenten, und die drei verbliebenen `is_terminal`-Aufrufer (`approvals.py:3315`, `scopes.py:341`, `state.py:1612`) fragen alle die Archiv-Regel, nicht „ist das noch Arbeit" — keine halb angewandte Änderung. Der Docstring benennt den ungepatchten Konsumenten ausdrücklich; das ist Hausregel 3 richtig herum.
* **`ruff check team-kits/kernel tools`** in der Kopie: „All checks passed!".
* **Zahlen in neuen Kommentaren**: keine alternde Zählung; alle neuen Kommentare zeigen als Zeiger auf Item-Ids.

## NEGATIVE BEFUNDE — NICHT GEMESSEN

* Die Rot-zuerst-Läufe von 17 der 23 geschlossenen Reihen (H109, H127, H184/H111, H48, H154, H142, H148, H143, H141, H71, H52, H197, H126, H130, H156, H164, BUG-0032) habe ich **nicht** einzeln nachgefahren — nur ihre Benennung mechanisch geprüft.
* Kein Lauf mit echten Hook-Prozessen gegen ein von mir gebautes Projekt; alle Messungen gehen gegen die importierten Kernelmodule und die echte Kommandofläche der Kopie.
* Protokollabschnitte 155–206, 352–494, 700–747 ungelesen.
* Von den 21 nicht geschlossenen Reihen habe ich **H106, H171, H60, H179, H183, H108, H197** gegen ihr Item bzw. den Code geprüft; **H155, H170, H58, H133, H157, H54, H110, H134, H44, H56, H132, H86, H84, H79, H76** habe ich nur gelesen und nicht gemessen. Mein Eindruck zu diesen (ohne Messung, deshalb keine Befunde): H133, H110, H134, H157, H54 lesen sich als echte Welt-/Plattformgrenzen mit tragfähigem deutschem Satz; H155, H170, H58 sind **in-repo-Vertragsänderungen mit Migration** — das ist Arbeit in diesem Repo, kein Limit, und darf nicht als „später" enden.
* **Eigener Fehlgriff, offengelegt**: Ich hatte zwischendurch `approval_mint_is_wired` mit einem RELATIVEN Root `False` gemessen und für einen Regress gehalten. Falsch — `ProjectState` absolutiert den Root (`state.root = C:\…\tree\project_memory`), kein Aufrufer übergibt einen relativen; wired = True. Kein Befund.

---

## URTEIL: **FAIL**

**Blockierend für die Runde:**

* **B1** — eine in dieser Runde als geschlossen gemeldete Lücke gewährt die billige Sprosse auf einem Satz, der einen Test verneint; Rot reproduziert. BUG-0278 darf so nicht in Batchzeile 1 stehen.
* **B3** und **B4** — zwei Kommentare behaupten einen Zustand, den der Code nicht hat (B3 alarmierend, B4 alarmierend). Hausregel 3 ist auch dann ein FAIL-Grund, wenn der Code stimmt; beide sind ein Absatz Arbeit.

**Benannte Reste (in die Löcherliste, mit Mechanismus, nicht mit den zwei Schreibweisen):**

* Die **Präfix-Klasse** von `_unify` (B3, zweiter Teil): ein Scope-Eintrag ohne Wildcard wird vom Gate als Verzeichnis-Präfix gelesen und von `_unify` als Literalpfad — jede Paarung „globfrei × Glob" ist über einem leeren Baum blind. 6 gemessene Paare.
* **B2** (vorangestellte Präposition, Über-Verweigerung), **B5** (Numerus und Frage/Karte-Deckung der Freigabefrage), **B7** (Einordnung von H171/H60), **B8** (Zählung).
* **B6/H106** und **S2/H108**: beides in-repo. Sie gehören in die Arbeit der Runde oder vor den Nutzer als ausdrückliche Ausnahme — nicht in eine Gruppe, deren Überschrift „kein Defekt" bzw. „Vertragsänderung" sagt.
* **B9** gehört dem Lead: EVD-0367 (Strom B) trägt `result: pass` für BUG-0263 ohne benennenden Knoten.