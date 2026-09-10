# FR-0089 — Strang C: unsere eigenen Zahlen (Generation 3/4/5) und die Routinen-Frage

Recherche-Rolle C von drei parallel gestarteten Sonnet-Rechercheuren unter FR-0089 (A = externe
Evidenz, B = externe Praxis, C = dieser Strang). Nur lesend; **eine** Datei geschrieben, dieselbe.

**Methodik-Hinweis vorab, weil er beide Teile trägt:** Wo eine Zahl nicht gemessen werden konnte,
steht das hier so, wie es die Quellen selbst sagen — sinngemäß TSK-0126s eigener Satz "lieber keine
Zahl als eine erfundene". Klassifikationen von Befunden in "Prosa/Code", "Leser liest weniger als
sein Docstring behauptet", "Koordination" und "echter Produktdefekt" sind, wo nicht schon so im
Quelltext benannt, **meine eigene Lektüre** dieser Sitzung — keine im Repo geführte Kennzahl. Das
wird unten an jeder Tabelle wiederholt, nicht nur hier.

---

## TEIL 1 — Unsere eigenen Zahlen (Generation 3, 4, 5)

### 1.1 Generation 3 (TSK-0120, Merge-Commit `6704221`, Retrospektive `DEC-0070`)

Quelle der Stromzeile: `project_memory/staging/TSK-0120/merge-protocol.md` Abschnitt 9 ("Die
(g)-Tabelle der Generation 3"), Zeile für Zeile übernommen:

| Strom | Stufe | Erst-Bericht | Prüfrunden (erste Runde B/M/N) | Nacharbeits­runden | Prüfrunden gesamt | Tokens Umsetzer / Prüfer | Spawn → PASS |
|---|---|---|---|---|---|---|---|
| A Board | Fable-Entwurf (4 Phasen) + Opus-Bau | Entwurf 07:22–09:56; Bau ~4 h 30 | B2/M2/N7 | 4 | 4 | ~810 k (Bau) + ~690 k (Entwurf) / ~495 k | ~9 h 15 |
| B Büro | Opus | ~2 h 20 | B2/M2/N6 | 4 | 4 | ~745 k / ~525 k | ~7 h 30 |
| C Freigaben | Opus | ~3 h 20 (zwei Nähte mitten in der Runde) | B2/M2/N7 | 2 | 3 | ~650 k / ~690 k | **~13 h** (kritischer Pfad) |
| D Texte | Opus | ~2 h 17 | B1/M5/N3 | 2 | 2 | ~495 k / ~355 k | ~5 h 30 |
| E Design | Opus | ~3 h 30 | B1/M5/N4 | 3 | 3 | ~475 k / ~360 k | ~9 h 45 |
| Merge | Opus | — | — | 1 | steht zum Protokollzeitpunkt aus | siehe Bericht | ~4 h, davon ~1 h 40 reine Suitenlaufzeit |

**Generationssumme laut Retrospektive `DEC-0070`:** ~53 h Stream-Wandzeit auf dem kritischen Pfad
(C ~13 h), **~4,6 Mio Umsetzer-Tokens** und **~2,4 Mio Prüfer-Tokens**, Merge zusätzlich ~4 h 15 /
~530 k Tokens. (Die Summe der Einzelzeilen oben ergibt für die Bauphase allein ~3,2 Mio — die
Differenz zu 4,6 Mio ist im Wesentlichen A's Entwurfsphase von Fable, ~690 k, die DEC-0070 in die
Gesamtsumme einrechnet, das Merge-Protokoll aber getrennt ausweist.)

**Wiederkehrende Fund-Klassen dieser Generation** (Wortlaut aus `DEC-0070`, Klassenlabel von mir
angehängt):

| # | Fund | Wo | Meine Klasse |
|---|---|---|---|
| 1 | Der ungefragte volle Suitenlauf — fünf gemessene Vorkommen, zusammen ~5 h der Generation; jeder Umsetzer nannte es, keiner wurde gestoppt | D, B, C, E (zweimal) | **Koordination/Verfahren** (kein Gate erzwang DEC-0050 zu diesem Zeitpunkt) |
| 2 | "Ein Wächter, der Kommandozeilen liest, öffnet mit jeder Verengung die nächste Klasse" (H144: Punkt → Unterverzeichnis → `cd` im Argument → `cd`, das nie landet → `cd`, das landet aber nicht handelt), 4 Prüfrunden | B | **Echter Produktdefekt**, schrittweise freigelegt (sicherheitsrelevante Lücke) |
| 3 | "Der Fix hat seine eigene Gegenlücke" — jede Runde öffnete in der Gegenrichtung eine kleinere Lücke, von der nächsten Runde gefangen | E, A, C | **Echter Produktdefekt** (durch den Fix selbst eingeführt) |
| 4 | "Ein benannter Test, der nicht scheitern kann" — vier Fälle (Teilstring-Fenster, Kommentar nennt einen Test, der die Landkarte nicht liest, zwei von drei Feldern ungedeckt, Ankunft nach Typ statt Stärke) | E, A (×3) | **Prosa vs. Code** — genau die Klasse, die `CLAUDE.md` "teurer als kein Test" nennt |
| 5 | Acht Befunde GEGEN DEN SCHNITT (was der Lead vor dem Zuschnitt nicht gemessen hatte: erzwungene Kopie, veraltetes Item im Bereich, VERSION-Behauptung falsch, geteilte Dateien nicht genannt, zwei Stolperdrähte sehen ihren Defekt nicht) | Lead | **Koordination/Lead-Ordnungsfehler** |
| 6 | Drei Orchestrator-Fehler (eine "queued"-Zustellung als Ergebnis gelesen = ~5 h Leerlauf auf C's kritischem Pfad; zwei widerlegte Auftragssätze) | Lead/Orchestrator | **Koordination** |
| 7 | Elf Merge-Befunde, davon vier aus dem Volllauf — **keiner** war in irgendeinem Einzelstrom sichtbar (DEC-0063 (1) bestätigt) | Merge-Runde | **Koordination/Naht** (nur über Ströme hinweg sichtbar) |

### 1.2 Generation 4 (TSK-0126, Merge-Commit `b7f282e`, Retrospektive `DEC-0080`)

Quelle: `project_memory/staging/TSK-0126/merge-protocol.md` Abschnitt 9 ("(g) — die Zeile je Strom
für die Rückschau der Generation 4"):

| Strom | Stufe | Runden (Bericht + Nacharbeiten) | Prüfungen | Tokens Umsetzer / Prüfer | Wandzeit gearbeitet / Spanne | Leerlauf durch Absturz |
|---|---|---|---|---|---|---|
| G4-1 TSK-0121 | Opus | 1 + 2 Nacharbeiten + 2 Abschlüsse | 5 (FAIL/FAIL/FAIL o. Blocker/FAIL o. Blocker/**PASS**) | ~1,45 M (Schätzung) / ~2,2 M | ~12–13 h (Schätzung) / ~20 h 15 | 4 Abstürze |
| G4-2 TSK-0122 | Opus | 1 + 3 Nacharbeiten | 4 (FAIL/FAIL/FAIL nur Pflicht 6/**PASS**) | ~731–750 k / ~1,66 M | ~4 h 40 gearbeitet, ~1 h 45 reine Rechenzeit / zwei Kalendertage | 4 Abstürze |
| G4-3 TSK-0123 | Opus | 1 + 3 Nacharbeiten | 3 (FAIL/**PASS**/**PASS**) | ~740 k / ~850 k | ~4 h 10 / ~20 h | ~11 h |
| G4-4 TSK-0125 | Opus | 1 + 2 Nacharbeiten + Abschluss | 3 (FAIL/FAIL/**PASS**) | ~0,9–1,07 M (Schätzung) / ~897 k | ~4 h 40 / ~20 h | 3 Resumes von der Platte |
| Merge TSK-0126 | Opus | 1 Bericht + 3 Nacharbeiten | 3 abgeschlossen (**FAIL, FAIL, FAIL mit einem Befund**), kurze Runde 4 stand aus | Umsetzer: **keine Messung möglich** (Prozess liest eigenen Verbrauch nicht — "lieber keine Zahl als eine erfundene"); Prüfer: in den drei Berichten | 04:4x → 20:00 ≈ ~15 h 15, davon ~10 h Suiten-/Rig-Läufe | keiner |

**Generationssumme laut `DEC-0080`:** Jeder Strom arbeitete 4–13 h innerhalb einer ~20-h-Spanne mit
~11 h Leerlauf durch **vier harte Host-Abschaltungen** (Windows Kernel-Power 41, ausgelöst von einer
16-Kern-Vollastmessung, die neben den anderen Strömen lief); **~4 Mio Umsetzer-Tokens** (Schätzungen,
wo der Prozess seinen Verbrauch nicht lesen kann) und **~5,6 Mio Prüfer-Tokens**; der Volllauf des
Merges fand beim ersten Mal **435 von 4 682 Tests rot**.

**Wiederkehrende Fund-Klassen dieser Generation:**

| # | Fund | Häufigkeit | Meine Klasse |
|---|---|---|---|
| 1 | "Ein Leser, der weniger liest, als sein Docstring behauptet" / "ein Zähler statt einer Identifikation" | G4-3: 5 von 7 Prüferbefunden; G4-1: die tautologische Verengungsoption + ein Wächtertest, der sein Objekt INS Projekt legt; G4-2: die CLI-Prüfung, die ihr eigener benannter Test nicht misst, `hole_type()` liest den halben Vertrag; G4-4: ein Test, der für die Pin-Zeile nicht scheitern kann; **über 80 Erwähnungen der Klasse in 16 Prüfberichten** | **Prosa vs. Code / Leser schwächer als Docstring** — die mit Abstand dominante Klasse dieser Generation |
| 2 | "Der Fix öffnet die nächste Kante" (Merge-Runde: Bestandsleser, den ein `capture SR` einschaltet; die Klammer, die der Glob-Leser nicht sieht; die EVD-Referenz außerhalb des Repos — drei Runden) | Merge | **Echter Produktdefekt**, durch den vorherigen Fix eingeführt |
| 3 | "Eine Aufzählung, wo der Dateikopf eine Eigenschaft behauptet" (`glob.has_magic` ohne `{`, `if item_type == TSK`, die "options_that_narrow"-Liste) | mehrere | **Prosa vs. Code** |
| 4 | Der ungefragte Volllauf trat in den EINZELSTRÖMEN **nicht** wieder auf (Gate gebaut, FR-0086/DEC-0070(4) griff) — aber der erste Volllauf des Merges fand 435 Rote aus zwei neuen Kernel-Verweigerungen, die keiner der Ströme liest (Z10) | Merge | **Koordination/Naht** (Reichweite eines Kernel-Vertrags nicht vor dem Spawn gemessen) |
| 5 | Neun Auftrags-/Lead-Fehler (Z1–Z9): eine Lastmessung vor vier Abschaltungen behauptet "gemessen"; ein bereits widerlegter Auftragssatz ein zweites Mal übernommen (Z2); eine Datei fehlt in der Nahttabelle; Schreibschritte als Ergebnis verlangt, die keine Rolle liefern darf; extrapolierte Uhrzeiten; ein Bereichswiderspruch im selben Item; ein vierter Verfassungssatz ohne Übergabe; "Volllauf vor Stempel" produzierte ~25 falsche Rote; keine Naht für die Reichweite eines Kernel-Vertrags | Lead (Zuschnitt/Auftrag) | **Koordination/Lead-Ordnungsfehler** — Z2 ist derselbe Fehlertyp wie in Generation 3, zum zweiten Mal |

### 1.3 Generation 5 (noch NICHT gemergt — Merge-Item `TSK-0133` steht als DRAFT, Stand 2026-09-06)

**Wichtiger Vorbehalt:** Anders als Generation 3 und 4 ist diese Generation zum Zeitpunkt dieser
Recherche **nicht abgeschlossen**. `TSK-0132` ist geschlossen (PASS), `TSK-0130` und `TSK-0131`
haben noch offene Runden (`TSK-0130` Runde 2 mit einem Rest, `TSK-0131` Runde 4 angekündigt). Die
Zahlen unten sind darum ein Zwischenstand, kein Generationsabschluss wie bei DEC-0070/DEC-0080 — es
gibt noch keine `DEC`-Retrospektive für Generation 5.

**TSK-0132 (G5-3, Büro-Paket) — GESCHLOSSEN**, Quelle: `staging/TSK-0132/stream-protocol.md`
Abschnitt 12 "(g)":

| Feld | Wert |
|---|---|
| Stufe | Fable-5.1-Vorgänger (vom Nutzer gestoppt, `DEC-0081`) → Opus 5, effort high |
| Wandzeit, gelesen | Vorgänger 0:46 (21:11→21:57); dieser Umsetzer 5:46 gearbeitet über eine Spanne 21:11→2026-09-06 10:34 = **13:23** |
| Runden | 4 Lieferungen (1 Bericht + 2 Nacharbeiten + 1 Abschluss) gegen 3 Prüfungen: **FAIL, FAIL, PASS** |
| Tokens | Sitzungssumme aus Budget-Zähler-Differenzen: **~630 k** (Bericht ~452 k, Nacharbeiten+Abschluss zusammen ~130 k). Einzelne Log-Zeilen nennen für Nacharbeit 1 "~499 k total" und für Nacharbeit 2 "~602 k total" — das liest sich als **kumulierter** Zwischenstand seit Spawn, nicht als Rundenkosten; die 630-k-Zahl aus der eigenen (g)-Zeile ist die genauere, weil sie die Zählregel nennt. Beide Angaben stehen hier, weil die Abweichung selbst eine Aussage über die Datenqualität ist. |
| Mutationen (rot-zuerst) | 53 eigene (20 vom Vorgänger, 33 von diesem Agenten), alle rc 1; dazu 35 Mutationen des Prüfers über drei Runden |
| Eigene Funde vor jeder Prüfung | 10 Defekte im vorgefundenen Paket (D1–D10, u. a. Absturz statt Verweigerung, ungeprüfte projektgeschriebene Zahlen, stille Annahme einer unbekannten USt-Kategorie) |

**TSK-0132 Fund-Klassifikation** (14 benannte Befunde über drei Runden, meine Einteilung):

| Klasse | Anzahl | Beispiele |
|---|---|---|
| Echter Produktdefekt | 9 | B1 (Annahme, was die Buchungszeile nicht buchen kann), B2 (Lückenverweigerung druckt einen Pfad, den das Skript selbst verweigert), B5 (geerbter Backtick-Paarungsdefekt, rot-zuerst blockiert), B6 (fünf Tracebacks), R2 (`a_value` schwächer als `money()`), R3 (E-Rechnungs-Erkennung zu lax), R4 (Buchungszeile bricht bei Sonderzeichen im Namen), V3-1/V3-2 (schmale Prüfung, Rundungs-Konvention) |
| Prosa vs. Code | 5 | B3 (Exit-Code-Tabelle falsch), B4 (sechs Verweigerungen ohne Test, Vertrag behauptet Deckung), B7 ("erfindet keine Gebühr/Frist/Absender" — falsch), R1 (Default angeblich entfernt, drei Sätze behaupten es, Test prüft nur den leeren Fall), V3-3 (Zeiger nennt nicht beide Tests) |

**TSK-0130 (G5-2, Watcher/Leiter/Eskalation) — LAUFEND**, letzte volle (g)-Zeile in
`staging/TSK-0130/stream-protocol.md` Abschnitt 11 deckt nur Bericht + erste Nacharbeit ab (der
Strom lief danach in Rundenlog `generation-5-streams.md` weiter: Verify Runde 2 "FAIL nur bei
R2-1", ein konsistenter Nachschnitt, eine "Deklaration" für die Cloud-Routine). Tokens laut
Rundenlog: Bericht ~465 k, Nacharbeit 1 + Messung ~649 k, Deklaration ~782 k — Summe der
Umsetzerseite bislang **~1,9 Mio** (nicht abgeschlossen); Prüferseite: Runde 1 ~320 k, Runde 2
~471 k = **~0,79 Mio** bislang.

Der teuerste Einzelfaden in diesem Strom ist nicht ein Code-Fehler, sondern **die Routinen-Frage
selbst**: die Nachricht des Nutzers ("Wie jetzt auch: über eine Claude Routine!") löste eine eigene
Mess-Runde aus (DEC-0084 "erst messen"), einen Versuch, eine Cloud-Routine über die
`RemoteTrigger`-API anzulegen, der an einer **undokumentierten Schnittstellenform** scheiterte
(DEC-0086), und am Ende die Erkenntnis `BUG-0266`/`H184`: der Project-Auditor/Watcher-Mechanismus
der Kits **meldet sich selbst als fällig**, kann sich aber **nicht selbst starten** — die
Genehmigungsarten `routine`/`analysis`, die die Verfassungen nennen, existieren in der installierten
CLI nicht. Allein die Nacharbeit 1 + Messung dieses Strangs kostete **~10 h 56** Wandzeit.

**TSK-0131 (G5-1, Bestandsbereinigung) — LAUFEND, Runde 4 angekündigt**, letzte (g)-Zeile in
`staging/TSK-0131/stream-protocol.md` Abschnitt N19:

| Feld | Wert |
|---|---|
| Stufe | Opus 5, effort high |
| Runden | 1 Bericht + 2 Nacharbeiten + 1 Abschlussrunde, **4 Prüfungen (FAIL/FAIL/FAIL/offen)** |
| Wandzeit | Vorgänger 21:21–22:07 (Fable); dieser Umsetzer 2026-09-05 22:10 bis 2026-09-06 ~17:00 — rund **14 h**, davon grob 5 h Suiten-/Rig-Läufe |
| Tokens | im Prozess selbst nicht lesbar; Log-Zeilen nennen Bericht ~546 k, Nacharbeit 1 "~814 k total", Nacharbeit 2 "~896 k total" — auch hier ist unklar, ob "total" kumulativ seit Spawn oder je Runde meint; ich übernehme die Zahlen wörtlich, ohne die Differenz zu erzwingen |
| Mutationen | 27 rot in der ersten Runde, je fünf/sechs weitere je Nacharbeit |

**TSK-0131 Fund-Klassifikation** (Auswahl über drei Runden, meine Einteilung):

| Klasse | Beispiele |
|---|---|
| Echter Produktdefekt | falsche tote Zeiger auf frischen Gerüsten (39/27/30, weil die Kit-Erkennung nur nach Verzeichnisnamen filtert); `AC-4` schließt nur `[]`, nicht `''`/`[None]`/`['   ']`; leere Formen (`work: []` etc.) rutschen durch und unterdrücken die Warnung; der Quittungsfilter verwirft die Trägerwarnung für JEDE aktive Entscheidung |
| Prosa vs. Code | der Sweep-Test kann nicht scheitern (behauptet nur, dass eine Teilzeichenkette in beiden Ausgängen vorkommt); eine ungemessene Behauptung über die Spawn-Fläche in `harness-implementer.md`; der SKILL-Zeiger-Test akzeptiert jeden Fettdruck-Absatz, der "ladder" enthält; die Validator-Zahlen im Protokoll sind veraltet; die Bestandstabelle weicht in drei Zeilen vom echten Bestand ab |
| Koordination | die PM-SKILL behauptet etwas, das erst der Merge von G5-2 wahr macht (Naht vorweggenommen); `migrate.py`-Behauptung außerhalb des erlaubten Bereichs |

### 1.4 Berechnungen

**Tokens je ausgelieferter Abnahmebedingung.** Nur für Generation 5 sauber berechenbar, weil dort
jeder Strom explizit `AC-1..AC-N` führt (Generation 3/4 zählen Abnahmebedingungen nicht in den
gelesenen Protokollen — eine erfundene Zahl wäre hier falsch, keine ungefähre):

| Strom | AC-Zahl | Umsetzer-Tokens bislang | Tokens/AC (grob, Strom nicht fertig bei 0130/0131) |
|---|---|---|---|
| TSK-0132 (6 AC, geschlossen) | 6 | ~630 k (Sitzung gesamt) | **~105 k/AC** |
| TSK-0130 (7 AC, laufend) | 7 | ~1,9 M bislang | **~271 k/AC**, und steigt noch |
| TSK-0131 (7 AC, laufend, Runde 4 offen) | 7 | ~0,9–2,3 M je nach Lesart von "total" | **~128–329 k/AC**, Spanne wegen der Kumulativ-Frage oben |

Der einzige **fertige** Wert ist TSK-0132 mit ~105 k Tokens je Abnahmebedingung. Die beiden anderen
sind Zwischenstände eines noch offenen Stroms und würden am Ende höher liegen, nicht niedriger.

**Anteil der Prüfer-Tokens an der Summe:**

| Generation | Umsetzer | Prüfer | Prüfer-Anteil |
|---|---|---|---|
| 3 | ~4,6 M | ~2,4 M | **~34 %** |
| 4 | ~4 M (Ströme) | ~5,6 M | **~58 %** — der Prüfer kostete in Generation 4 MEHR als der Umsetzer |
| 5 (Zwischenstand, nur die drei Streams, unvollständig) | TSK-0132 ~630 k allein zurechenbar; 0130/0131 Umsetzer noch offen | TSK-0132 hat keinen separaten Prüfer-Tokenwert in der (g)-Zeile (der Prüfer misst extern); TSK-0130 Prüfer ~0,79 M bislang, TSK-0131 Prüfer-Tokens nicht durchgehend beziffert | nicht sauber berechenbar, Generation läuft |

Der Sprung von 34 % auf 58 % zwischen Generation 3 und 4 ist selbst ein Fund: die Prüfrunden wurden
NICHT billiger, obwohl DEC-0070 genau das für Generation 4 vorschreiben wollte (Regel 6: der Prüfer
greift zuerst die Leser-Klasse an) — die Leser-Klasse war dann mit über 80 Erwähnungen die
dominante Fund-Klasse und hat die Prüfkosten nach oben getrieben, nicht gesenkt.

**Anteil der Runden/Funde, die auf Prosa oder Koordination statt auf einen echten Produktdefekt
entfielen.** Eine saubere Angabe ist nur auf **Fund-Ebene** ehrlich möglich, nicht auf
**Runden-Ebene** — eine Nacharbeitsrunde schließt fast immer mehrere Funde verschiedener Klassen
gleichzeitig, und keine der gelesenen Quellen ordnet eine ganze Runde EINER Klasse zu (Ausnahme:
`TSK-0130` Runde 2 "R2-1" ist explizit als der alleinige Grund für eine Nacharbeit benannt — ein
Lead-Ordnungsfehler). Auf Fund-Ebene, mit den Zählungen aus 1.1–1.3 zusammengefasst:

| Generation | Prosa/Code | Koordination/Lead/Naht | Echter Produktdefekt (inkl. progressiv freigelegter) |
|---|---|---|---|
| 3 | 1 Klasse (4 Fälle) | 3 Klassen (ungefragter Volllauf, 8 Zuschnitt-Befunde, 3 Orchestrator-Fehler, 11 Naht-Befunde) | 2 Klassen (Wächter-Kette H144, Fix-Gegenlücke) |
| 4 | 2 Klassen (Leser-schwächer-als-Docstring >80 Erwähnungen, Aufzählung-vs-Kopfbehauptung) | 2 Klassen (9 Auftrags-/Lead-Fehler Z1–Z9, Merge-Naht Z10/435 Rote) | 1 Klasse (Fix öffnet nächste Kante, 3 Runden) |
| 5 (TSK-0132 als einziger fertiger Strom) | 5 von 14 benannten Funden (36 %) | 0 dominant, aber die Routinen-Frage in TSK-0130 ist reine Koordination/Infrastruktur | 9 von 14 (64 %) |

Für Generation 4 ist die zahlenmäßige Dominanz eindeutig: die Leser-Klasse allein wird in den
sechzehn Prüfberichten **über 80-mal** erwähnt — mehr als jede andere einzelne Fund-Art in dieser
Generation. Für Generation 3 und 5 ist die Verteilung gemischter; TSK-0132 ist bislang der einzige
Strom, bei dem echte Produktdefekte in der Mehrheit sind.

**Die drei teuersten Einzelfunde** (nach Wandzeit-Wirkung, weil das die einzige Größe ist, die über
alle drei Generationen konsistent gemessen wurde):

1. **Generation 4 — die vier harten Host-Abschaltungen** durch eine unkoordinierte
   16-Kern-Vollastmessung, die neben den anderen Strömen lief: **~11 h Leerlauf** über die ganze
   Generation, eigene DEC-0080-Regel (4) dagegen geschrieben.
2. **Generation 4 — der erste Volllauf des Merges** fand 435 von 4 682 Tests rot, weil zwei neue
   Kernel-Verweigerungen Suiten trafen, die kein Strom liest (Z10): trug wesentlich zu den
   **~10 h Suiten-/Rig-Laufzeit** innerhalb der ~15 h 15 Merge-Wandzeit bei.
3. **Generation 3 — Strom C's verlorene Fertigmeldung + ein HTTP 529**: **~5 h Leerlauf** allein
   auf dem kritischen Pfad dieses einen Stroms, der dadurch von einer mit A/B/D/E vergleichbaren
   Dauer auf ~13 h anwuchs — der teuerste einzelne Orchestrator-Fehler der drei gelesenen
   Generationen.

### 1.5 Was die Zahlen stützen — und was sie NICHT können

**Was sie stützen:** In allen drei Generationen sind **Koordination** (Nähte, Lead-Zuschnittfehler,
Orchestrator-Zustellung) und **Prosa-vs-Code-Funde** (Kommentare/Tests, die mehr behaupten, als der
Code hält) zusammen eine sehr große, in Generation 4 die klar dominante Fund-Klasse — genau das
Muster, das der Nutzer in seiner Frage vermutet ("viele Runden", "nicht so gut"). Der Prüfer-Anteil
an den Gesamtkosten ist gestiegen, nicht gesunken, obwohl die Kits genau darauf zielende Regeln
erlassen haben (DEC-0070 Regel 6). Der teuerste Einzelfund in allen drei Generationen war jedes Mal
ein **Verfahrens-/Koordinationsproblem**, kein Codefehler im engeren Sinn.

**Was sie NICHT können:** Es existiert **kein kontrolliertes Experiment** in diesem Repo — keine
dieser drei Generationen wurde jemals parallel mit einem einzelnen Fable-Agenten an derselben
Aufgabe gegengemessen. Die Zahlen sagen, was die Pipeline für SICH SELBST kostet und woran; sie
sagen nichts darüber, ob ein einzelner Fable dieselben 14 (Generation 3) bzw. 4 (Generation 4)
Produktziele in kürzerer Zeit, mit weniger Tokens oder in besserer Qualität geliefert hätte — dafür
gibt es in diesem Repo keine Messung, nur die Beobachtung des Nutzers aus anderen Projekten
(Frontend-Vergleiche). Außerdem sind die drei Generationen nicht untereinander vergleichbar wie ein
A/B-Test: die Stufen wechselten zwischen den Generationen (Opus in 3 und 4, Fable/Opus-Mischung in
5 nach `DEC-0081`), der Zuschnitt änderte sich (Datei-Eigentum in 3, Produktziele in 4/5), und jede
Generation hat aus der vorherigen gelernt (DEC-0070 → DEC-0080 → laufende Regeln in 5) — ein Teil
des gemessenen Fortschritts ist also Lerneffekt der Pipeline selbst, nicht ein Beweis dafür, dass
die Pipeline-Form richtig gewählt ist. FR-0089s eigentlicher Auftrag — ein Experiment, das dieselbe
Aufgabe einmal solo und einmal über die Pipeline laufen lässt — ist damit weiterhin offen; diese
Recherche liefert nur das Kostenbild der Pipeline selbst, keinen Vergleich.

---

## TEIL 2 — Claude-Code-Routinen auf diesem Host

### 2.1 Was auf DIESEM Host tatsächlich liegt (lesend geprüft, 2026-09-06)

**Der lokale Hintergrund-Daemon** (`C:/Users/zenti/.claude/daemon.status.json`,
`daemon.log`, `jobs/`):

- `daemon.status.json`: `"workers": {}` — der Daemon läuft, hat aber **keine aktiven
  Hintergrund-Arbeiter**.
- `daemon.log`: zeigt ausschließlich Supervisor-/Auth-Refresh-Zeilen und Hintergrund-Bash-Worker
  (`bg spawned … (slash)`, `(spare)`, `(fleet)`) — das ist die Infrastruktur für
  `run_in_background`-Bash-Aufrufe **innerhalb** laufender Sitzungen, keine Terminplanung.
- `jobs/`: genau **ein** Job-Verzeichnis, `069441de` (Zeitraum 2026-08-07 bis 2026-08-24). Sein
  `state.json` zeigt eine ToDo-Liste und einen laufenden Test-Lauf einer früheren Lead-Sitzung
  ("TSK-0084 CR write-scope fix" usw.) — das ist die Historie einer **von Hand gestarteten**
  Sitzung, kein wiederkehrender Auftrag. Kein Eintrag heißt "radar-watcher" oder "codex-watcher" als
  eigener Auftrag; der Name taucht nur zweimal in der Zeitleiste auf, weil diese Lead-Sitzung den
  Watcher seinerzeit **von Hand gespawnt** hat.

Das deckt sich mit dem, was `generation-5-streams.md` (Log-Zeile 2026-09-06, TSK-0130) bereits
gemessen hatte: *"NOTHING starts it — no session cron, no OS task, no account routine (RemoteTrigger
list empty, twice), and the local Claude daemon's only job … is the timeline of an earlier lead
session that SPAWNED the watcher by hand, not a schedule."*

**Ein Fund, den diese Recherche zusätzlich zu TSK-0130 gemacht hat:** Unter
`C:/Users/zenti/.claude/scheduled-tasks/` liegt ein Verzeichnis **`radar-watcher/`** mit genau einer
Datei, `SKILL.md`:

```
---
name: radar-watcher
description: Weekly harness radar — repo health + Claude Code/community scan
---

You are the weekly radar-watcher for this repo (a multi-agent dev harness for Claude Code).
Follow .claude/agents/radar-watcher.md exactly. READ-ONLY on the codebase — only write under radar/.
1) Read radar/decided.md and the latest radar/*.md first so nothing is re-surfaced.
2) Repo health: run python tools/validate.py, python -m pytest tools/ -q, ruff check . — note any drift.
3) Scan Anthropic/Claude Code (...) and the agent community for genuinely NEW developments (...)
4) Write radar/<today YYYY-MM-DD>.md in the shape from radar/README.md (...)
5) Do NOT change code and do NOT commit — leave the report for me to triage.
```

Erstellt und letztmals geschrieben laut Dateisystem am **2026-06-30, 10:53** — seither unverändert.
Daneben liegt `scheduled_tasks.lock` (ein Sitzungs-Lock, zuletzt erneuert 2026-04-27) und
**keine** weitere Konfigurationsdatei zu Zeitplan oder Ein/Aus-Zustand in diesem Ordner.

Das ist — siehe 2.2 — exakt das Format, das die offizielle Doku für einen lokal in der
**Desktop-App** angelegten "Scheduled Task" beschreibt. Es beweist, dass **irgendwann** (Ende Juni)
ein solcher lokaler Auftrag für "radar-watcher" in der Desktop-App angelegt wurde. Es beweist
**nicht**, dass er heute noch aktiv ("Active" statt "Paused") ist oder überhaupt je gefeuert hat:
Zeitplan, Modell und Ein/Aus-Zustand stehen laut Doku ausdrücklich NICHT in dieser Datei, sondern
nur in der Desktop-App selbst — und diese Datei ändert sich laut Doku nicht, wenn der Auftrag
feuert oder pausiert wird, sodass ihr unverändertes Datum seit Juni **kein** Beleg für Inaktivität
ist. Eine durchsuchbare Konfigurationsdatenbank der Desktop-App mit dem Zeitplan-Zustand wurde unter
`%LOCALAPPDATA%\Claude` und `Claude-Data` nicht gefunden (nur Logs); Windows' eigener
Aufgabenplaner (`schtasks /query`) trägt **keinen** Eintrag mit "claude", "radar" oder "anthropic"
im Namen — ein separates OS-Level-Scheduling existiert auf diesem Host also nicht.

### 2.2 Was die offizielle Dokumentation sagt (`code.claude.com/docs/en/routines` und
Nachbarseiten, abgerufen 2026-09-06)

Claude Code kennt heute **drei** verschiedene Terminierungswege, mit genau dieser Gegenüberstellung
in der Doku selbst:

| | Cloud-Routine (`/schedule`, claude.ai/code/routines) | Desktop Scheduled Task | `/loop` (Sitzungs-gebunden) |
|---|---|---|---|
| Läuft auf | Cloud, standardmäßig von Anthropic verwaltet | dem eigenen Rechner | dem eigenen Rechner |
| Braucht Rechner an | Nein | Ja | Ja |
| Braucht offene Sitzung | Nein | Nein | Ja |
| Übersteht Neustart | Ja | Ja | Nur bei `--resume`/`--continue`, wenn nicht abgelaufen |
| Zugriff auf lokale Dateien | Nein (frischer Klon) | Ja | Ja |

**Cloud-Routine (`/schedule`).** Zitat aus der Doku: *"A routine is a saved Claude Code
configuration: a prompt, one or more repositories, and a set of connectors, packaged once and run
automatically. Routines execute on Anthropic-managed cloud infrastructure … so they keep working
when your laptop is closed."* Sie klont bei jedem Lauf das Repo frisch von GitHub, schreibt auf
einen `claude/`-Branch und kann eine Pull-Request öffnen — sie schreibt **nicht** direkt in den
lokalen Arbeitsbaum. Auslöser sind planbar (`Scheduled`, Mindestintervall 1 Stunde), per API
(`/fire`-Endpunkt) oder per GitHub-Ereignis. Erzeugt wird sie webseitig unter
`claude.ai/code/routines` oder per `/schedule` in einer interaktiven CLI-Sitzung — **beides
claude.ai-Konto-Objekte**, kein Dateisystem-Artefakt im Repo.

**Desktop Scheduled Task.** Zitat: *"A local task runs on your machine with direct access to your
files and tools, but only fires while the app is open and your computer is awake."* Und: *"To edit
a task's prompt on disk, open `~/.claude/scheduled-tasks/<task-name>/SKILL.md` … Schedule, folder,
model, and enabled state are not in this file: change them through the Edit form or ask Claude."*
Genau dieses Verzeichnis und genau diese Datei liegen auf diesem Host (2.1) — der Fund von 2.1 ist
also mit sehr hoher Sicherheit ein Desktop-Scheduled-Task, keine Cloud-Routine und kein
Session-Cron. Sein Nachteil steht auch in der Doku selbst: *"Tasks only run while the desktop app is
running and your computer is awake. If your computer sleeps through a scheduled time, the run is
skipped."* Für einen Nutzer, der überwiegend über die CLI/das Terminal arbeitet statt über die
offene Desktop-App, ist das ein Auslöser, der über Wochen nie feuert, ohne dass irgendetwas eine
Fehlermeldung zeigt.

**`/loop` und `CronCreate`/`CronList`/`CronDelete` (Sitzungs-gebunden).** Zitat: *"Tasks are
session-scoped: they live in the current conversation and stop when you start a new one … For
scheduling that survives independently of any session, use Routines … a Desktop scheduled task, or
GitHub Actions."* Und zur Begrenzung: *"Recurring tasks automatically expire 7 days after
creation."* Das ist der Mechanismus, den `TSK-0130`s eigene Messung (2.3) als "session cron" führt
und der für einen wöchentlichen Watcher **strukturell ungeeignet** ist — er stirbt spätestens nach
sieben Tagen und sowieso beim Schließen der Sitzung.

### 2.3 Abgleich mit den harness-eigenen Messungen (`DEC-0084`, `DEC-0085`, `DEC-0086`,
`BUG-0266`/`H184`)

Der Watcher-Strang `TSK-0130` hat dieselbe Frage bereits VOR dieser Recherche live am System
gemessen, mit Prozess-Beobachtung statt nur Dokumentenlektüre, und kam zu einem im Kern gleichen,
aber schärferen Bild:

- Der **Project-Auditor**-Mechanismus der Kits (das Vorbild, das der Nutzer meinte: *"So wie auch
  der Project Auditor laufen sollte"*) IST als Routine registriert (`session_status` beim
  Sitzungsstart, ISO-Wochen-Takt) und meldet sich korrekt als fällig ("ROUTINE DUE … propose it to
  the user and spawn it yourself; no hook starts a run") — **kann sich aber nicht selbst starten**,
  weil die Genehmigungsarten `routine`/`analysis`, die die Kit-Verfassungen dafür vorsehen, in der
  installierten CLI **nicht existieren** (ungültige Auswahl, `H111` zum zweiten Mal gemessen). Das
  ist `BUG-0266`/`H184`.
- Ein Versuch, die Cloud-Routine automatisiert per `RemoteTrigger`-Werkzeug anzulegen, scheiterte an
  einer **undokumentierten** Endpunkt-Form (`DEC-0086`): *"the endpoint validates an UNDOCUMENTED
  shape (measured: top-level `schedule` rejected; 'one of job_config or session_request must be
  set'; session_request rejects `branch` and `prompt`, requires `worker`)"*. Der `claude-code-guide`-
  Agent bestätigte danach dieselbe Doku-Lage wie oben: Routinen werden nur über die Web-UI oder
  `/schedule` in einer interaktiven Sitzung angelegt, und der einzige öffentliche API-Endpunkt ist
  `/v1/claude_code/routines/{id}/fire` — Anlegen selbst ist keine öffentliche API.
- Konsequenz in `DEC-0086`: der **Nutzer** legt die beiden Routinen (radar, codex) manuell in der
  Web-UI an (`claude.ai/code/routines`) aus einer vom Strom gebauten Deklaration (Zeitplan, Prompt,
  Branch-Namen), der Lead liest sie danach nur noch über `RemoteTrigger list/get` zurück und
  schreibt `radar/routine.json`.
- Der `RemoteTrigger`-Kontostand war zum Messzeitpunkt **leer** (zweimal geprüft) — es existiert
  **kein** aktives Cloud-Routine-Objekt für radar-watcher oder codex-watcher auf dem Konto.

Das deckt sich mit 2.1/2.2 und ergänzt es um einen Punkt, den `TSK-0130` selbst nicht geprüft hat:
den **Desktop-Scheduled-Task** unter `~/.claude/scheduled-tasks/radar-watcher/`. Dieser wurde von
`TSK-0130`s Messung nicht gefunden (dessen Log spricht nur von "no session cron, no OS task, no
account routine") — vermutlich, weil er ein viertes, in der eigenen Aufzählung nicht bedachtes
Format ist. Er ändert das Gesamturteil nicht (siehe 2.4), schließt aber eine Lücke in der bisherigen
harness-eigenen Recherche: Es gibt sehr wohl EIN Artefakt auf diesem Host, das aussieht wie der
Versuch, genau diese Routine über die Desktop-App einzurichten — nur dass dieser Weg strukturell
voraussetzt, dass die Desktop-App offen und der Rechner wach ist, was für einen CLI-first-Alltag
untypisch ist und von keiner der 14 bisherigen radar-Berichte belegt wird.

### 2.4 Urteil: Läuft der radar-watcher heute routiniert?

**Nein — mit Beleg, nicht Vermutung.** Vier unabhängige Prüfungen zeigen dasselbe:

1. `daemon.status.json`/`daemon.log`/`jobs/`: kein wiederkehrender Auftrag, nur ein von Hand
   gestarteter Sitzungsverlauf.
2. `schtasks /query`: kein Windows-Task-Scheduler-Eintrag.
3. `RemoteTrigger` (Cloud-Konto): leer, zweimal von `TSK-0130` geprüft.
4. Der einzige gefundene Terminierungs-Kandidat, `~/.claude/scheduled-tasks/radar-watcher/SKILL.md`,
   ist ein Desktop-Scheduled-Task-Artefakt ohne lesbaren Ein/Aus-Zustand, unverändert seit
   2026-06-30, und selbst wenn aktiv, feuert er laut Doku nur, **während die Desktop-App offen und
   der Rechner wach ist** — eine Bedingung, die 14 von 14 bisherigen radar-Berichten (alle laut
   `generation-5-streams.md` von Hand oder durch eine Lead-Sitzung ausgelöst) nicht erklärt.

Die `.claude/agents/radar-watcher.md`-Rollendatei selbst behauptet nur *"Triggered by the weekly
schedule (or manually)"* — ein Satz ohne einen einzigen durchsetzenden Mechanismus dahinter, exakt
das Muster, das `CLAUDE.md` in diesem Repo als verbotenen "Kommentar, der Schutz behauptet, den der
Code nicht baut" beschreibt.

### 2.5 Welche Routinen-Form passt zu "wöchentlicher Watcher, der einen Bericht nach `radar/`
schreibt"

Ein wöchentlicher Watcher mit lokalem Repo-Lesezugriff (`tools/validate.py`, `pytest tools/`, `ruff
check .`) UND dem Wunsch, dass er auch bei geschlossenem Rechner zuverlässig läuft, passt in
**keine einzelne** der drei Formen ohne Kompromiss:

- **Cloud-Routine** — läuft zuverlässig ohne offenen Rechner, aber klont das Repo frisch von GitHub
  (kein lokaler Zustand, kein direkter Schreibzugriff auf den Arbeitsbaum) und legt ihr Ergebnis in
  einer Session bzw. einem `claude/`-Branch/PR ab, nicht direkt in `radar/` auf der Platte. Für
  einen Watcher, der NUR liest und einen Bericht committet, ist das dennoch die einzige Form, die
  wirklich "ohne Session" und "übersteht einen Neustart" beides erfüllt — genau das, was `DEC-0085`
  am Ende auch gewählt hat (radar/codex als Cloud-Routine, vom Nutzer in der Web-UI angelegt).
- **Desktop Scheduled Task** — hat lokalen Dateizugriff und kann direkt nach `radar/` schreiben,
  aber nur solange die Desktop-App offen und der Rechner wach ist; für einen Alltag ohne dauerhaft
  offene Desktop-App ist das der unzuverlässigste der drei Wege trotz des vorhandenen Artefakts.
- **`/loop`/Session-Cron** — ungeeignet für "wöchentlich", weil Aufgaben nach sieben Tagen ablaufen
  und mit der Sitzung sterben.

**Empfehlung, die zur bereits getroffenen Entscheidung `DEC-0085`/`DEC-0086` passt:** Cloud-Routine
bleibt die richtige Form für den wöchentlichen Watcher — sie ist bereits als Weg gewählt, nur noch
nicht vollzogen (die zwei Routinen sind laut `RemoteTrigger`-Messung noch nicht angelegt). Das
lokale Desktop-Task-Artefakt unter `~/.claude/scheduled-tasks/radar-watcher/` ist entweder ein
verwaister erster Versuch aus dem Juni oder ein zweiter, redundanter Weg — die Desktop-App müsste
geöffnet und der Zustand ("Active"/"Paused") dort geprüft werden, um das zu klären; das ist mit den
hier verfügbaren, rein lesenden Mitteln (Dateisystem, `schtasks`, Web-Doku) nicht weiter aufklärbar
und gehört als eigener kleiner Prüfpunkt an den Nutzer zurück, nicht als Annahme in diesen Bericht.

---

## Quellen

**Teil 1:** `project_memory/staging/TSK-0120/merge-protocol.md` §9; `project_memory/decisions/active/DEC-0070.yaml`;
`project_memory/staging/TSK-0126/merge-protocol.md` §9, §10, §12–14; `project_memory/decisions/active/DEC-0080.yaml`;
`project_memory/staging/generation-5-streams.md` (ganzes Rundenlog); `project_memory/staging/TSK-0130/stream-protocol.md` §11;
`project_memory/staging/TSK-0131/stream-protocol.md` §N19; `project_memory/staging/TSK-0132/stream-protocol.md` §12.

**Teil 2 (lokal, lesend, 2026-09-06):** `C:/Users/zenti/.claude/daemon.status.json`, `daemon.log`, `jobs/069441de/state.json`,
`jobs/069441de/timeline.jsonl`, `C:/Users/zenti/.claude/scheduled-tasks/radar-watcher/SKILL.md`, `scheduled_tasks.lock`,
`schtasks /query` (Windows-Aufgabenplaner, keine Treffer), `C:/Offline Repos/AgentAndSkills/.claude/agents/radar-watcher.md`,
`C:/Offline Repos/AgentAndSkills/radar/README.md`.

**Teil 2 (Web, abgerufen 2026-09-06):** [Automate work with routines](https://code.claude.com/docs/en/routines),
[Run prompts on a schedule](https://code.claude.com/docs/en/scheduled-tasks),
[Schedule recurring tasks in Claude Code Desktop](https://code.claude.com/docs/en/desktop-scheduled-tasks).
