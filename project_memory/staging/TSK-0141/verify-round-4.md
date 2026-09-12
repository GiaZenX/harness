# Prüfbericht TSK-0141 (PR-0012, Order 3b, Strom A Kernel) — Runde 4 — **PASS**

Prüfer: `harness-verifier` (Opus, high), 9 min, +25 k Token. Als Text geliefert, vom Lead hierher gelegt (2026-09-12 14:03, Uhr gelesen). Reste 1 und 2 als Löcher aufgenommen (siehe Rundenlog), Rest 3 in die Retrospektive.

## Prüfbericht Runde 4 (Abschluss) — TSK-0141

Neu gespiegelt (2931 Dateien), S4 in meiner Kopie angewendet (`apply_s4.py`, BEFORE-Zeile genau einmal, die vier `%s` unberührt).

---

## GEMESSEN

**F3 — geschlossen.** `tools/test_light_kit.py:775-794` hält jetzt beide Zahlen als ausgeschriebene Nominalphrase gegen die ausgelieferte (`subject == _card_subject(kind, count)`, `:863`). Meine zwei Runde-3-Mutationen, die in Runde 3 grün blieben, sind rot:

```
Singular als Hauptsatz  ("eine Lücke bleibt offen")  -> 1 failed in 12.69s
Plural mit fünftem Verb ("%d Lücken stehen offen")   -> 1 failed in  4.62s
```

Der Docstring benennt den Preis selbst (jede Umformulierung der Karte macht den Test rot) und begründet ihn — für einen Text, den der Nutzer unterschreibt, die richtige Richtung.

**F1 — geschlossen.** Über den echten Eingang `acceptance_is_test_shaped` (`probe_dispatch7.py`):

```
ok got=False | Neither of the tests goes red after the rename
ok got=False | No fix ships; nor does a test go red
ok got=True  | noch ein Test wird rot
ok got=True  | Es gibt einen Fix; noch ein Test wird rot
```

Zur Frage, ob `noch` fehlen darf: **ja, einverstanden.** Die Asymmetrie liegt in den Sprachen, nicht im Leser — englisch `nor` verneint allein, deutsch `noch` ist ein Additionspartikel („noch ein Test" = ein weiterer). `noch` zu listen würde jede Zusage mit diesem Wort unnötig verweigern, und die öffnende Hälfte (`weder`) fängt die Konstruktion ohnehin. Die Tabelle sagt das an Ort und Stelle mit einer gemessenen Zeile je Paar.

**F2 — geschlossen, mit dem benannten Rest genau dort, wo er angekündigt ist.** Alle vier `of`/Genitiv-Zeilen verweigert. Die einzige Abweichung meiner 24 Zeilen ist der erklärte Rest:

```
XX got=True want=False | Das Ergebnis wird ohne den Nachweis der Tests rot
ok got=False           | Das Ergebnis wird ohne die Hilfe einer Probe, die rot wird, erreicht
```

`dispatch.py:2956-2961` nennt ihn in der gefährlichen Richtung zuerst („`der` und `einer` sind auch Nominativ und Dativ"). Gemessen ist er also weder größer noch kleiner als behauptet.

**F5 — geschlossen.** `tools/test_research_chain.py:285-291` und `tools/test_e2e.py:499-507` tragen das Paar, beide mit einem Warum-Kommentar, der sagt, dass `returncode == 0` sonst nichts misst. Die argv-Form gegen den echten Parser: `EVD-0406 test: pass`, rc 0.

**F4 — geschlossen.** Mit S4 angewendet:

```
python -B -m pytest .claude/hooks/test_gates.py -q -k commit
-> 51 passed, 503 deselected in 321.17s   (exit 0)
```

Das ist genau die Zahl, die C gemeldet hat. `REVIEWED_BY` steht einmal (`:473`) und speist die neun argv-Stellen. Der Docstring von `test_gate3_remedy_is_executable_and_opens_the_commit` (`:1556-1572`) sagt jetzt ausdrücklich, was er **nicht** misst — die argv wird gebaut und nicht aus dem gedruckten Text geparst, die beiden unterscheiden sich heute um genau das Flag-Paar, die Reparatur ist die Nutzer-Naht S4, und ein Test, der die gedruckte Zeile wirklich ausführt, kann erst danach grün sein. Das ist die ehrliche Form der Lücke, die ich in Runde 3 gemeldet habe.

**EVDs.** EVD-0404 (BUG-0278) und EVD-0405 (BUG-0271) kommen durch `naming_tests.coverage_blocker`. Über alle 73 Datensätze bleibt **nur EVD-0361** ohne benennenden Knoten, und der ist `result: blocked` — die drei Datensätze von Strom B, die ich in Runde 2/3 gemeldet hatte, sind repariert.

**Batchzeilen.** Einmal neu gefahren: rc 0 / rc 0 / rc 0, 27 Ids, jede genau einmal.

**Frage 1.** Jetzt beantwortbar: jedes der vier Wörter ist in einem Satz erklärt, und zwar über seine Wirkung („überspringt die Architekturrunde"), die drei Streuner aus den Tests sind als solche benannt, und jede Option trägt ihre Kosten. Ein Nicht-Entwickler kann hier entscheiden.

**Reverts sauber.** `tools/test_ladder.py` + der Kartenknoten: 51 passed in 89,32 s.

---

## NICHT GEMESSEN

* Kein Lauf der breiten Suiten (`tools/test_hooks*.py`, volle Suite) — das ist die Lieferrunde.
* Strom B schreibt weiter; die Kits sind ungestempelt.
* Ob `-k commit` auch OHNE den S4-Patch 51 grün ist, habe ich nicht gegengeprüft (C's Fix liegt in den argv-Stellen, der Patch im gedruckten Text) — für das Urteil unerheblich, weil beide Hälften einzeln gemessen sind.

---

## URTEIL: **PASS**

Alle vier Befunde aus Runde 3 sind mit einem Rot geschlossen, das ich selbst gesehen habe, und die Frage an den Nutzer ist lesbar geworden.

Was die Runde als **benannte Reste** mitnimmt — jeder mit Mechanismus, keiner mit zwei Schreibweisen:

1. **Der mehrdeutige deutsche Genitiv** (`der`, `einer`) beendet ein Präpositionskomplement zu früh und kann die billige Sprosse kaufen. Im Code deklariert, gefährliche Richtung zuerst; gehört so auch in die Löcherliste, nicht nur in den Kommentar.
2. **Die gedruckte Abhilfe des Commit-Gates bleibt kaputt, bis der Nutzer S4 fährt — und nichts im Baum wird währenddessen rot.** Der Docstring sagt es; die Löcherliste muss es ebenfalls sagen, samt der Verstärkung, die danach möglich wird (ein Test, der die gedruckte Zeile wirklich ausführt).
3. **Das Verneinungs-Vokabular hat in vier Runden vier Löcher gehabt.** Das ist das Signal der Klasse selbst: ein Wortinventar über eine natürliche Sprache wird nie fertig. Der Stolperdraht hält beide Enden und sagt in seinem eigenen Docstring, dass er ein fehlendes Wort nicht sehen kann — mehr ist hier mechanisch nicht zu holen; jede weitere Runde an diesem Leser braucht einen Menschen mit Sätzen in der Hand.
4. Offen und beim Nutzer: die drei Entscheidungsfragen (H155, H170, H171), die Naht H183 (Installer), die sechs Welt-Grenzen der Gruppe C und die sieben Reihen der Gruppe D.