# Prüfbericht TSK-0141 (PR-0012, Order 3b, Strom A Kernel) — Runde 3 — **FAIL (eng, zwei Punkte)**

Prüfer: `harness-verifier` (Opus, high), 14 min, +49 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 13:35, Uhr gelesen). F4 gehört Strom C (test_gates.py), F5 test_e2e.py Strom B3. Abweichung von DEC-0096 (FAIL 3 → Stufe+1) bewusst: zwei der vier Befunde liegen in fremden Dateien, die übrigen sind je eine Zeile; Fable-Bauer sind seit dem Wort des Nutzers vom 2026-09-11 nicht tragbar — Opus bleibt.

## Prüfbericht Runde 3 — TSK-0141, Nacharbeit 2

Neu gespiegelt (2927 Dateien). Gelesen: Protokollabschnitt „Rework 2" (ab Zeile 1106) und `staging/TSK-0141/s4-gate-commit-evidence-patch.md`.

---

## BEFUNDE

### F1 — R1: das Paar ist zu, die EINZELNEN Hälften sind offen (gefährliche Richtung)

`team-kits/kernel/dispatch.py:2915` + `:3014-3018`. Gemessen über den echten Eingang `acceptance_is_test_shaped` (`probe_dispatch6.py`):

```
XX got=True want=False | Neither of the tests goes red after the rename
XX got=True want=False | No fix ships; nor does a test go red
```

`neither` ohne `nor` („neither of the tests") und `nor` ohne `neither` (der Anschlusssatz, den die Satztrennung an `;` ohnehin freistellt) sind in beiden Fällen gewöhnliche englische Verneinungen — und beide **kaufen die billige Sprosse**. Die drei Sätze aus Runde 2 sind dagegen erledigt (alle drei verweigert). Der Stolperdraht sagt in seinem eigenen Docstring, dass er ein FEHLENDES Wort nicht sehen kann (`tools/test_ladder.py:554-556`) — die Behauptung ist also ehrlich; die Lücke ist trotzdem gemessen und offen.

Nebenbefund in der billigen Richtung, benannt statt entdeckt: „neither here nor there the test goes red" (Idiom + Zusage) wird verweigert.

### F2 — R2: der Preis stimmt, der Kommentar nennt ihn zu eng

`team-kits/kernel/dispatch.py:2937-2942`. Der Kommentar nennt als Preis den deutschen Genitiv („ohne die Hilfe eines Tests"). Gemessen ist die Klasse größer und in beiden Sprachen gleich:

```
XX got=True want=False | Das Ergebnis wird ohne die Hilfe eines Tests rot
XX got=True want=False | Das Ergebnis wird ohne den Nachweis eines Tests rot
XX got=True want=False | The result goes red without the help of a test
XX got=True want=False | The result goes red without the support of any regression test
```

Nicht „der Genitiv", sondern: **jedes Komplement, dessen Nominalphrase eine zweite Nominalphrase enthält** — im Deutschen der Genitiv, im Englischen die `of`-Nachstellung. Ein Satz im Kommentar.

### F3 — R4: die „Form"-Zusicherung ist eine Vier-Verben-Liste und nur im Plural (blockierend, billig)

`tools/test_light_kit.py:831`:

```python
assert not re.search(r"für \d+ \w+ (bleiben|sind|werden|gehen)\b", approving), approving
```

Das Protokoll sagt, damit sei „a third phrasing of the same mistake is caught too". Gemessen — zwei Mutationen, die genau den Fehler aus Runde 2 wieder einbauen, bleiben **GRÜN**:

```
Singular als Hauptsatz  ("eine Lücke bleibt offen")   -> 1 passed in 1.41s
Plural mit anderem Verb ("%d Lücken stehen offen")    -> 1 passed in 1.46s
```

Der Singular kann von dem Muster gar nicht getroffen werden (kein `\d+`), und die Verbliste ist eine Aufzählung. Das ist ein benannter Test, der für den Fall, den er behauptet, nicht scheitern kann — nach Hausregel 4 der teurere der beiden Defekte. Minimalfix: gegen die Struktur prüfen, die der Satz haben MUSS (die Karte liest „… für <Nominalphrase>: …"), statt gegen vier Verben — z. B. verlangen, dass zwischen `für` und dem Doppelpunkt kein finites Verb ohne einleitendes Relativpronomen steht, oder schlicht beide ausgelieferten Formen (Singular und Plural) als Zeichenketten gegen die Nominalphrasen-Form prüfen.

### F4 — S4: der Patch repariert den TEXT, aber die Gate-Suite dieses Repos bleibt rot (blockierend)

Patch in meiner Kopie angewendet (`apply_s4.py`, die BEFORE-Zeile kommt genau einmal vor, die vier `%s` bleiben unberührt). Danach:

```
EVD-0403 review: pass        rc=0
```

Die gedruckte Abhilfe schreibt also wirklich eine Evidence. Die zweite Hälfte der Abnahme aber nicht:

```
python -B -m pytest .claude/hooks/test_gates.py -q -k commit
-> 3 failed, 17 passed, 503 deselected, 31 errors in 189.82s
```

Ursache, gemessen am Einzelknoten:

```
.claude\hooks\test_gates.py:6916: AssertionError
python scripts/harness.py evidence: error: the following arguments are required: --run-command, --run-scope
```

`.claude/hooks/test_gates.py` ruft die `evidence`-Oberfläche an **zehn** Stellen als echten Unterprozess auf (`:1560, :1584, :1616, :1641, :1659, :1980, :2067, :2553, :6911`) und trägt das Paar nur an einer (`:7333`). S2 hat damit nicht nur den gedruckten Satz zerbrochen, sondern die eigene Gate-Suite dieses Repos — und die Protokollzeile „why no test saw it" stimmt nicht: ein Test hat es gesehen, in der Suite, die weder in `pytest tools/` noch in einem Kit-Lauf mitläuft und die CLAUDE.md ausdrücklich getrennt startet. Die Datei gehört TSK-0143; S4 muss sie mitnehmen, sonst ist die Abnahme des Patches nicht erreichbar.

### F5 — die Grep-Behauptung ist falsch, und eine der Fundstellen ist Strom A's EIGENE Datei

`tools/test_research_chain.py:286-288` steht in TSK-0141s `allowed_scope` (Zeile 29 des Items) und schreibt einen echten Aufruf ohne das Paar, mit `assert recorded.returncode == 0`:

```python
recorded = project.harness(
    "evidence", "--kind", kind, "--result", "pass", "--related", "TSK-0001",
    "--summary", "Messlauf geprüft", "--artifact-ref", "staging/TSK-0001/lauf.log")
```

Dieselbe Form bei `tools/test_e2e.py:501-504` (Strom B). Beide Knoten konnte ich in meiner Kopie nicht fahren — die Fixture von `test_research_chain` stirbt auf diesem Host vorher an einem Bash-Pfad (`init_project_memory.sh`, rc 127) —, deshalb: **abgeleitet**, nicht Ende-zu-Ende gemessen; gemessen ist, dass genau diese Argumentliste am Parser rc 2 bekommt. Die übrigen Treffer meines baumweiten Greps habe ich einzeln gegengeprüft und verworfen: `gate_test_scope.py:709` schreibt die Flags über `%s` (zur Laufzeit korrekt), `cli.py:573` ist die Parserdefinition, die drei `templates/repo/scripts/harness.py:33` und die restlichen Testtreffer sind Prosa oder liegen außerhalb meines Suchfensters.

---

## NEGATIVE BEFUNDE — GEMESSEN

* **R1 Kern**: „Nothing makes a test go red", „Neither the test nor the probe goes red", „Weder ein Test noch ein Nachweis wird rot" → alle drei verweigert. „Weder hier noch dort schlaegt der Test fehl" ebenfalls.
* **Der Paar-Stolperdraht ist echt**: Mengengleichheit gegen `_CORRELATIVE_DENIERS` und die „zweite Hälfte ersetzt → Zusage"-Prüfung (`tools/test_ladder.py:589-598`). Rot-zuerst nachgefahren: Korrelative entfernt → **beide** Knoten rot, 2 failed in 2.66s.
* **R2 Kern**: alle vier meiner Runde-2-Zeilen verweigert, beide vorangestellten Formen wieder Zusagen; ein Determinativ, das NICHT in der Liste steht (`unseren`), kostet höchstens eine unnötige Verweigerung — gemessen in beiden Richtungen. Rot-zuerst: das Überspringen des öffnenden Determinativs entfernt → Knoten rot, 1 failed in 1.45s. Von 30 Zeilen 23 richtig; die 7 Abweichungen sind F1 (3), F2 (4) und das Idiom.
* **R4 Oberfläche**: „für eine Lücke, die offen bleibt: BUG-0136 …" und „für 2 Lücken, die offen bleiben: …" — Nominalphrase in beiden Zahlen, auf der echten Kommandofläche.
* **S4 Patch**: sauber anwendbar, Formatstring unverändert, Abhilfe schreibt `EVD-0403` rc 0.
* **Batchzeilen**: 27 Ids, rc 0 / rc 0 / rc 0.
* **EVD-0401/0402**: beide durch `naming_tests.coverage_blocker`; die Karte bindet die NEUEN Datensätze (`BUG-0271 (EVD-0402); BUG-0278 (EVD-0401)`). Ein Feld `supersedes` gibt es nicht — die Ablösung ruht auf „der neueste deckende Datensatz gewinnt"; gemessen, dass das trägt. Unverändert: EVD-0361 (blocked, korrekt) und drei EVDs von Strom B ohne benennenden Knoten (0370, 0387, 0390).
* **Reverts sauber**: `tools/test_ladder.py` + die zwei `test_light_kit`-Knoten → 52 passed in 66,31 s.

## DIE DREI DEC-FRAGEN

**Frage 2 und Frage 3: ja** — ein Nicht-Entwickler kann sie beantworten. Optionen mit Kosten, keine Fachwörter außer den Item-Nummern, und die Kostenzeile von Frage 3 A („eine Zeile, die nach dem Einbau eines Pakets niemand mehr schreiben kann") sagt genau das, was ihn später treffen würde.

**Frage 1: noch nicht ganz.** Sie verlangt vom Nutzer, ein Vokabular festzulegen, dessen Mitglieder nirgends erklärt sind — und eines der drei genannten Wörter (`technical_enabler`) ist gar keine Größe, während die Frage alle drei als „ein Wort für seine Größe" einführt. Ein Halbsatz je Wort („`technical_enabler` = Umbau unter der Haube, ohne sichtbares Ergebnis") macht sie beantwortbar.

---

## URTEIL: **FAIL** (eng, zwei Punkte)

**Blockierend:**

* **F4** — S4 macht den gedruckten Satz wieder richtig, aber die Abnahme, die der Patch selbst vorschreibt (`test_gates.py -k commit`), ist rot: zehn Aufrufstellen in `.claude/hooks/test_gates.py` tragen das Paar nicht. Der Patch muss die Datei mitnehmen (sie gehört TSK-0143), sonst ist die Naht nicht abnehmbar.
* **F3** — die Form-Zusicherung zu BUG-0271 kann für den Fall, den sie behauptet, nicht scheitern; zwei Mutationen des Originaldefekts bleiben grün.

**Benannte Reste (Löcherliste, mit Mechanismus):**

* **F1** — „ein Korrelativ ist als PAAR gelesen, seine Hälften stehen aber auch allein als Verneiner" (`neither of …`, anschließendes `nor …`); gefährliche Richtung, je eine Zeile.
* **F2** — „ein Komplement, dessen Nominalphrase eine zweite enthält, endet zu früh" — deutscher Genitiv UND englische `of`-Nachstellung; der Kommentar nennt nur die erste Hälfte.
* **F5** — `tools/test_research_chain.py:286-288` (Strom A's eigene Datei) und `tools/test_e2e.py:501-504` schreiben `evidence`-Aufrufe ohne das Paar; die Grep-Behauptung des Protokolls muss korrigiert werden.

Alles andere aus Runde 2 ist gemessen erledigt, jeweils mit einem Rot, das ich selbst gesehen habe.