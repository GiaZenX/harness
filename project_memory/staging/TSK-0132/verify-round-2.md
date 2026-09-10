# TSK-0132 (PR-0009, G5-3 Office) — Prüfbericht Runde 2

Rolle: `harness-verifier`. Frische Kopie ausserhalb des Repos:
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0132/verify/tree2` (Spiegel von `g5-office`, ohne
`.git`), frischer Basisexport `…/verify/base2` (`git archive b7f282e`). Eigenes Rig
`…/verify/rig2.py` — verweigert ausserhalb seines Verzeichnisses (DEC-0070), binär, prüft nach
jedem Lauf den SHA-256 der Originaldatei. Uhr: Start **2026-09-06 07:22:51**, Ende **07:57:57**.
Baseline in meiner Kopie: `tools/test_office_package.py` **62 passed in 58.63s**.

**Urteil: FAIL** — deutlich enger als Runde 1. AC-3, AC-4, AC-5, AC-6 bestanden; AC-1 und AC-2
fallen an vier Befunden, drei davon eine Zeile Fix.

Sieben Blocker der Runde 1 nachgemessen: **B1, B2, B3, B5, B6 geschlossen; B4 zu fünf Sechsteln;
B7 zu drei Vierteln.** Details unten.

---

## 1. Blockierende Befunde

### R1 — B7 ist zu drei Vierteln geschlossen: der argparse-Default `19` steht noch, und drei Texte sagen, er sei weg
`team-kits/office-team/templates/repo/scripts/letter_draft.py:373`:
`parser.add_argument("--vat-rate", default="19", help=…)`.

Gemessen (`test_r5b_the_vat_rate_default_the_protocol_says_is_gone`, Angebot **ohne** die Flagge,
`kleinunternehmer: false`):

```
offer WITHOUT --vat-rate: rc=0
    ['zuzüglich 19 % Umsatzsteuer: 19,00 EUR']
```

Damit steht wieder ein vom Kit gewählter Steuersatz im Kundenbrief. Drei Stellen behaupten das
Gegenteil:
* `letter_draft.py:25-27` — „Until 2026-09-06 four of them had a fallback in the code (`or 14`,
  `or "Sie"`, `or "Mit freundlichen Gruessen"`, **argparse `default="19"`**)" — drei sind weg, der
  vierte steht;
* `stream-protocol.md` §2 B7 — „`--vat-rate` no longer defaults to 19";
* `tools/test_office_package.py:1299` (Docstring des benannten Tests) — „had an argparse default
  of 19".

Der benannte Test misst die Behauptung **nicht**: `…:1305` übergibt `--vat-rate ""`, also den
Leerstring-Zweig, nie den fehlenden Flag. **Minimalfix:** `default=""` (der Refusal-Zweig
darunter ist fertig und gut formuliert) plus ein Fall im selben Test ohne die Flagge.

### R2 — `a_value` ist schwächer als der Leser, den es ersetzt: zwei Tracebacks und eine negative Umsatzsteuer im Kundenbrief
`letter_draft.py:77-90` fängt nur `(ValueError, ArithmeticError)` um `read(...)`; `Decimal("NaN")`
und `Decimal("Infinity")` sind gültige Decimals, und negative Werte prüft niemand.

Gemessen (`test_r5_a_value_shapes`):

```
--vat-rate 'NaN'      -> rc=1  ValueError: invalid literal for int() with base 10: 'nan'   (eur(), :87)
--vat-rate 'Infinity' -> rc=1  decimal.InvalidOperation                                    (:236)
--vat-rate '-19'      -> rc=0  DRAFT: ['zuzüglich -19 % Umsatzsteuer: -19,00 EUR', '**Gesamtbetrag: 81,00 EUR**']
--vat-rate '1e2'      -> rc=0  DRAFT: ['zuzüglich 1E+2 % Umsatzsteuer: 100,00 EUR']
```

Das ist B6s Klasse (Traceback statt Verweigerung) und B7s Klasse (eine Zahl im Kundenbrief, die
niemand so meinte) im **neuen** Leser. Zwei Leser derselben Datei können es schon: `money()`
(`:75-82`) prüft `is_finite()` und Nichtnegativität — die Mahngebühr geht durch `money` und ist
darum sauber (gemessen: `fee` als Wort → Verweigerung) —, und `einvoice_extract._amount:141-146`
trägt die NaN-Lektion samt Messung in seinem eigenen Kommentar. Der Docstring
`letter_draft.py:22-31` formuliert eine **Definition** („every value that reaches the customer's
letter … where the record is unreadable it refuses and names the field") und nennt zwei Tests;
beide decken diesen Fall nicht. **Minimalfix:** `a_value` prüft `is_finite()` und die Shape sagt,
ob negativ erlaubt ist — oder der Satz geht durch `money`.

### R3 — `_is_an_einvoice` ist „parst als XML", nicht „ist eine der zwei Syntaxen"; die Vertragsseite verspricht das Zweite
`team-kits/office-team/templates/repo/scripts/einvoice_extract.py:284-295` — Docstring: „The root
element name when `data` parses as **one of the two syntaxes** this reader knows"; der Rumpf ist
`return _local(ET.fromstring(data))` für **jedes** parsende XML.

Gemessen (`test_r7_a_pdf_whose_xml_is_not_an_invoice`), ein ZUGFeRD-PDF mit `factur-x.xml` (echte
Rechnung) **plus** `aaa-note.xml` = `<note>hello</note>`:

```
invoice + note attachment -> rc=1
[einvoice] this PDF carries 2 embedded e-invoice XML files (aaa-note.xml, factur-x.xml); which one
the document is about is not this reader's guess — refused
```

Der Anhang „note" wird als E-Rechnung gezählt und benannt. `docs/office/invoice-app-docking-point.md:24`
verspricht der App-Seite: „it parses every attachment and **takes the one that IS an e-invoice** …
a PDF carrying two is refused". PDF/A-3 erlaubt weitere Anhänge; ein solches PDF ist jetzt „not
judgeable". Die gebrauchte Definition steht 20 Zeilen tiefer in `parse_xml` (`CrossIndustryInvoice`
/ `Invoice` / `CreditNote`) — der Fix ist ein Vergleich gegen diese Menge, plus ein Testfall mit
einem Nicht-Rechnungs-Anhang: der benannte Test
`::test_a_pdf_carrying_two_invoice_attachments_is_refused_not_guessed` hängt **zwei Rechnungen** an
und kann den zu weiten Leser darum nicht sehen (meine Mutation `v2-n2-attachment-choice` rc 1 misst
nur die Zwei-Treffer-Verweigerung, nicht die Auswahl).

### R4 — „a verdict never promises a booking that cannot happen" gilt für das Dict, nicht für die Zeile, die daraus wird
`invoice_intake.py:120-126` (ROW_FLAGS-Kommentar, „ONE declaration, TWO readers") und die
Verweigerung im `judge` versprechen es absolut. Gemessen
(`test_r2_backstop_render_after_validate`), Käufername `--doc-type`:

```
== buyer '--doc-type': intake rc=0
   ROW counterparty='--doc-type'
   PRINTED: … --counterparty --doc-type --invoice-no RE-2026-0004 …
   LEDGER rc=2 usage: ledger_add.py [-h] --year YEAR --direction {income,expense} …
```

`validate_row` urteilt über das Dict (Wert nicht leer → in Ordnung); die **argv**, die daraus
gerendert wird, zerlegt argparse anders. Praktisch trifft es nur einen Namen aus **einem** Token
mit führendem `-` (gemessen: `-Nord GmbH` mit Leerzeichen bucht rc 0, weil argparse ein Wort mit
Leerzeichen als Wert liest) — die Behauptung ist trotzdem absolut formuliert. **Minimalfix:** vor
dem Rendern jeden Wert prüfen, der mit `-` beginnt (oder `--` als Trenner setzen), plus ein
Testfall.

**Und die zweite Hälfte derselben Stelle:** `_shell()` quotet nur bei Leerraum und escapet kein
`"`. Gemessen, Käufer `He said "hi"`:

```
PRINTED: … --counterparty "He said "hi"" …          (die Shell liest: He said hi)
LEDGER  rc=0 [ledger_add] appended … income He said "hi" …
```

Die gedruckte Zeile bucht also etwas anderes als `--book`. Die Definition dafür hat dieses Paket
selbst geschrieben: `team-kits/kernel/documents.py::quoted_for_a_command_line` tauscht genau dieses
Zeichen. Zweite, schwächere Schreibweise derselben Antwort (F8/D5-Form).

---

## 2. Nicht blockierend

* **R5 — eine Leser-Mutationsrichtung bleibt grün (DEC-0080 (6)).** `destination_of` sagt „exactly
  one is needed"; meine Mutation `v2-b4-plan-rule-count` (`if len(hits) != 1` → `< 1`, also zwei
  Regeln stillschweigend akzeptiert) lässt **alle 62 Tests grün**. Der Zweig funktioniert
  (gemessen, `test_r9_two_plan_rules_for_one_class`): zwei Regeln für `sales_invoice` →
  `rc=1 … 2 plan rule(s) file the class 'sales_invoice' … exactly one is needed`. Es fehlt der
  Fall, nicht der Code. (Nebenbei: die Remedy sagt auch bei zwei Regeln „add the rule".)
* **R6 — BUG-0263s Zahlen sind konventionsabhängig.** Mit meinem eigenen zaunbewussten Leser über
  denselben Korpus: **475 gesehen / 529 vorhanden / 54 ungesehen** gegenüber 486/525/39 im Item
  (ich blende Zaunblöcke ganz aus, das Item zählt sie mit). Mechanismus und Grössenordnung stimmen
  überein; die Zahl im Item sollte niemand als exakt zitieren.
* **R7 — `1e2` als Steuersatz** rendert „zuzüglich 1E+2 % Umsatzsteuer" in den Kundenbrief; mit dem
  Shape-Fix aus R2 erledigt.

---

## 3. Was ich nachgemessen habe und was hält

**B1 geschlossen.** Beide Fixtures der Runde 1 (`test_r1_b1_the_two_round_one_fixtures`):

```
== 19 % stated, tax 0.00: rc=2 … the booking line this document produces is one the ledger itself
   refuses -- … net 999.00 * (1 + 19.00%) = 1188.81 != gross 999.00 …
== no tax breakdown at all: rc=2 … states a VAT amount of 40.70 (net 214.20, gross 254.90) but
   carries no VAT breakdown (BG-23) …
```
Mutationen `v2-b1-bg23` und `v2-b1-ledger-backstop` je **rc 1**.

**B2 geschlossen.** Die Verweigerung nennt jetzt die Reihenfolge, die das Skript geht („hand its
own invoice in first (the 380 …), then the 381 … Handing the 381 in on its own is refused");
Mutation auf genau diesen Halbsatz (`v2-b2-gap-remedy`) rc 1, der Test führt beide Reihenfolgen
wirklich aus.

**B3 geschlossen, als Definition.** Sechs eigene Sonden (`test_r4_b3_exit_codes`):
```
no plan rule (project)        rc=1     broken triple (document)      rc=2
unknown category (project)    rc=1     unorderable number (document) rc=2
two ranges match (project)    rc=1     `first` as a word (project)   rc=1
```
Die Vertragsseite §3 trägt die Regel und beide Fallisten; sie decken sich mit der Messung.

**B4 zu fünf Sechsteln.** `v2-b4-category-check`, `-placeholder`, `-range-ambiguity`,
`-mixed-rates` je rc 1; `v2-b4-plan-rule-count` grün → R5.

**B5 geschlossen, und die Kette stimmt.** Die neue, eng gefasste Prüfung geht für **beide**
Dokumente rot: `v2-b5-field-pointer` rc 1 (`docs/office-kit-from-field.md`) und
`v2-b5-contract-pointer` rc 1 (`docs/office/invoice-app-docking-point.md`). Kontrolle gefahren:
derselbe Fund im Feldbericht lässt die repo-weite Prüfung **grün**
(`v2-b5-shipped-reader-stays-green` rc 0, `1 passed`) — genau die Kette, die BUG-0263 beschreibt.
Das Item trägt `limits`, `hole_number: H181` und Modulpräfixe.

**B6 geschlossen.** `--today gestern`, `level: "zwei"`, `days_after_due: "vierzehn"`, ein
Ledger-`doc_date` `02.08.2026` und `valid_days` als Wort: je rc 1, benannte Stelle, kein Traceback;
Mutation `v2-b6-value-reader` rc 1 (6 failed).

**B7 zu drei Vierteln.** `address`, `closing`, `offer.valid_days` — entfernt, leer, nur Leerzeichen,
`null`, und sogar der ganze `offer:`-Block weg: je **rc 1 mit `apply-proposal`-Route**, nichts im
Ausgangsfach (`test_r6_a_term_empty_versus_absent`, sieben Varianten). Mutation
`v2-b7-term-fallback` rc 1. Der vierte Wert ist R1.

**N1/N2/N5/N6.** `v2-n1-destination-taken`, `v2-n2-attachment-choice`, `v2-n5-decimal-only`,
`v2-n6-recipient` je rc 1; die Ziel-Kollision wird verweigert und nennt `<invoice_no>` als Ausweg,
der bereits archivierte Pfad kollidiert nicht mit sich selbst. N2 hält, aber zu weit → R3.

**Humanizer.** Gemessen, nicht behauptet: mein Eingriff in einen **gerenderten** Text (Gedankenstrich
in den Angebotssatz) macht `::test_the_three_drafts_pass_the_countable_half_of_the_humanizer_bar`
rot (`v2-humanizer-emdash` rc 1). Gezählt werden Satzlängenstreuung, unspaced Em-Dash,
„nicht nur … sondern auch", Zusammenfassungsabsatz, eine Anredeform.

**AC-1 unter DEC-0082.** Keine Rollen-Verdrahtung im Kit (`correspondence-clerk` kommt in
`team-kits/office-team/**` nirgends vor, kein `presets.yaml`-Eintrag, kein `project_config`-Eintrag,
keine Leitersprosse); `DEC-0082` wird in drei Kit-Dateien zitiert (Verfassung, beide Skills) und
löst gegen den Hauptspeicher auf; die zwei Grenzen (kein zweiter Leser, keine Parallelproduktion)
stehen in Verfassung §5, `skills/correspondence/SKILL.md` und `skills/office-manager/SKILL.md`.
D14 (der Skill-Zeiger auf `project_memory/staging/TSK-0132/`) ist weg — gemessen: kein Treffer mehr.

**Naht DEC-0082 nachgerechnet.** Mit dem Prädikat des Tests selbst gegen den Hauptspeicher gefahren:
**83 Entscheidungen im Speicher, 322 Zeiger geurteilt, 0 unaufgelöst, 65 davon aus dem Büro-Kit** —
genau die Behauptung des Protokolls; der rote Test im Worktree liegt nur an dessen `b7f282e`-Stand
von `project_memory/`.

**H176.** Weiterhin geerbt: `git show b7f282e:docs/POST_V2_WISHLIST.md` trägt **0** `### H`-Einträge
(44 `### L`), und das Paket fügt keinen hinzu.

**Patch und Nähte.** 28 Dateien, **0 CR-Bytes**, keine VERSION-, keine repo-`project_memory`-Hunks;
`git apply --check` gegen einen frischen `b7f282e`-Export **rc 0**; nach dem Anwenden sind `tools/`,
`docs/` und `team-kits/` byte-identisch mit dem Paketbaum **bis auf die drei VERSION-Dateien**.
Alle sieben neuen Dateien liegen im Patch. `lead_package_sizes.json` = 59369 mit fünf
Journal-Schritten in `phase0-disposition.md` (15 TSK-0132-Zeilen, angehängt). Keine dev/research-
Datei ausser den VERSION-Stempeln. Office-Stempel `2026.09.06-2`.

**Rig und Protokoll.** 43 `redfirst-*.log`, **jedes rc 1**, jede deklarierte Mutation hat ihr Log
und umgekehrt (nachgezählt). Protokoll §0 trägt die Selbstkorrektur zum nicht gemessenen
`test_hooks`-Lauf der Runde 1. `ruff check .` im Paketbaum: einziger Fund liegt in **meiner**
Angriffsdatei.

---

## 4. Ergebnis je Abnahmekriterium und je Pflicht

| AC | Urteil | Grund |
|---|---|---|
| **AC-1** (DEC-0082) | **FAIL** | Workflow korrekt und ohne Rollen-Verdrahtung gebaut, Humanizer gemessen, drei von vier Termen wirklich ohne Default — aber R1 (Steuersatz-Default steht, drei Texte sagen das Gegenteil, der benannte Test misst es nicht) und R2 (NaN/Infinity → Traceback, `-19` → negative Umsatzsteuer im Kundenbrief) |
| **AC-2** | **FAIL** | B1, B2, B3, N1, N5 gemessen geschlossen; fällt an R3 (Anhang-Eigenschaft weiter als Docstring und Vertrag) und R4 (gerenderte Buchungszeile vs. geprüftes Dict, plus die Quotierung der gedruckten Zeile); R5 als benannter Rest |
| **AC-3** | **PASS** | unverändert gegenüber Runde 1, dort gemessen |
| **AC-4** | **PASS** | Tabelle mit Urteil je Punkt; N3 korrekt geschlossen (der Schlussabsatz sagt jetzt genau, was die Tabelle trägt und welcher Test es hält); der Anker geht rot, und die repo-weite Prüfung als Kontrolle grün |
| **AC-5** | **PASS** | unverändert, Runde 1 gemessen |
| **AC-6** | **PASS** | Remedies weiter ausgeführt und angenommen; die Anhang-Auswahl (dort mitgeführt) trägt R3, das aber die Andockstelle betrifft und dort steht |
| **Pflicht 7** | **fast PASS** | 43 Mutationen rc 1 nachgezählt, 16 neue je Leser; eine Richtung bleibt grün (R5). Löcher: BUG-0263 sauber erfasst, BUG-0248/0258/0259 in §9 benannt |
| **Pflicht 8** | **PASS** | Naht-Tabelle stimmt mit der Messung, DEC-0082-Naht nachgerechnet, keine Spiegel-Schreibung |
| **Pflicht 9** | **PASS** | Patch, Protokoll, Rig, Stempel, Scratch-Ort, kein Commit/Push/Install |

## 5. Ausdrücklich nicht gemessen

* Die grossen Suiten des Umsetzers (`3338 passed` über neun Suiten, `614 passed / 2 failed` in der
  Kernel-Gruppe) habe ich **nicht** wiederholt — Hostregel und Rollenteilung; nachgerechnet habe ich
  die **Erklärungen** beider roten Tests (H176 geerbt, DEC-Naht) und die Log-Bilanz des Rigs.
* `tools/validate.py`, `bump_kit_version.py` (Stempel bleibt provisorisch, gehört zum Merge).
* Die Humanizer-Hälfte, die kein Zähler misst — korrekt als Pflicht benannt.
* Token- und Zeitangaben des Protokolls (§10) sind von hier nicht prüfbar.

---

**Verdikt: FAIL.** Blockierend sind R1, R2, R3, R4 — alle vier sind Ein-Zeilen-Fixes plus je ein
Testfall, und drei von ihnen sind Behauptungen, die weiter reichen als der Code. R5 gehört als
fehlender Fall in denselben Nachlauf, R6/R7 als Notiz. Alles andere aus Runde 1 ist gemessen
geschlossen.
