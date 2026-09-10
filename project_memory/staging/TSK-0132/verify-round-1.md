# TSK-0132 (PR-0009, G5-3 Office) — Prüfbericht Runde 1

Rolle: `harness-verifier`. Gemessen gegen den laufenden Code in einer Kopie **ausserhalb** des Repos:
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0132/verify/tree` (Spiegel des Worktrees `g5-office`
ohne `.git`), Basisexport `…/verify/base` (`git archive b7f282e`). Eigenes Rig
`…/verify/rig.py` — verweigert ausserhalb seines eigenen Verzeichnisses (gemessen: rc 3), öffnet
jede Datei binär, stellt nach jedem Lauf den SHA-256 des Originals wieder her.
Uhr gelesen: Start **2026-09-06 00:04:08**, Ende siehe §7.

**Urteil: FAIL.** AC-3, AC-5, AC-6 bestanden; AC-1 (Kern), AC-2 und AC-4 nicht.

---

## 1. Blockierende Befunde

### B1 — Die Andockstelle nimmt Rechnungen an, die ihre eigene Buchungszeile nicht buchen kann; die fehlenden Zahlen erfindet sie
`team-kits/office-team/templates/repo/scripts/invoice_intake.py:382` (`rate = rates[0] if rates else "0"`)
und `:402` (`treatment = treatments[0] if treatments else ("standard" if numeric_rate else "exempt")`).

Gemessen (verify/tree, eigener Angriff `test_a10_the_printed_booking_line_is_one_the_ledger_takes`):

```
== 19 % stated, tax 0.00: intake rc=0
   ROW: net=999.00 rate=19 gross=999.00 treatment=standard
   LEDGER rc=1 [ledger_add] REFUSED: this entry would make the ledger invalid — NOTHING was written
== no tax breakdown at all: intake rc=0
   ROW: net=214.20 rate=0 gross=254.90 treatment=exempt
   LEDGER rc=1 [ledger_add] REFUSED: this entry would make the ledger invalid — NOTHING was written
```

Im zweiten Fall steht im Dokument `tax 40.70`, das Skript setzt `--vat-rate 0 --vat-treatment exempt`
— beide Werte stehen nirgends im Dokument, der zweite wird aus dem ersten abgeleitet. Damit sind drei
geschriebene Zusagen falsch:
* `invoice_intake.py:19` „Everything it decides it prints; **nothing it decides is a guess**."
* `docs/office/invoice-app-docking-point.md:67` „both are read off your document or the document is
  not booked — **the kit never fills either from the other**."
* PR-0009 Invariante „Money figures reconcile or refuse".

Die Kette läuft in einer Sitzung durch: Verdict ACCEPTED → Ablage über die Pipeline → `--book` scheitert.
**Minimalfix:** in `judge`/`vat_of` die Identität `net × (1+rate) = gross` gegen **eine** Definition
prüfen (aus `ledger_add.validate_row` gelesen, nicht zweitgeschrieben) und ein Dokument mit
`tax != 0` ohne BG-23 refusen statt Rate/Treatment zu füllen. Test: zwei Fälle in
`test_a_planted_violation_is_refused_with_the_figures_named`.

### B2 — Die Lücken-Verweigerung druckt einen Weg, den dasselbe Skript verweigert (BUG-0079-Klasse im BUG-0079-Strom)
`invoice_intake.py:332` druckt: „…if the missing ones were cancelled, **their cancellation documents
arrive first**." Gemessen (`test_a2_a_cancelled_number_gap_and_the_remedy_it_prints`):

```
GAP    rc=2  gap in range shop_a / 2026: last issued 3, arriving 5, 1 number(s) missing in between (4..4)
             -- refused. Remedy: … if the missing ones were cancelled, their cancellation documents arrive first.
STORNO rc=2  the credit note cancels 'RE-2026-0004', and no booked income row carries that number
             -- refused: the original is booked first, or was never ours.
```

Der genannte Weg ist genau der, den `document_type_check` refust: eine 381 auf eine nie gebuchte
Nummer. Für ein storniertes, nie eingegangenes Dokument gibt es damit keinen begehbaren Weg — die
BUG-0041-Sackgasse, gegen die dieser Strom sonst argumentiert. **Minimalfix:** den Satz auf den Weg
umschreiben, den der Code akzeptiert (die stornierte 380 kommt zuerst herein, dann ihre 381 —
`docs/…/invoice-app-docking-point.md` §4.2 sagt das bereits: „import it first"), und den Fall in §2
der Vertragsseite nennen. Test: der Storno-Fall als eigener Parameterfall.

### B3 — Die Exit-Code-Tabelle des Vertrags widerspricht dem Code
`docs/office/invoice-app-docking-point.md:127` führt „no filing rule for the class" unter **Exit 1**
(„not judgeable … a configuration gap"). Gemessen (`test_a14_the_unguarded_refusals_still_work`):

```
no plan rule for the class: rc=2  [intake] REFUSED inbox/x.xml: 0 plan rule(s) file the class 'kein_typ' …
```

Der Vertrag ist das maschinenlesbare Versprechen an ein anderes Projekt; die App verzweigt auf dem
Exit-Code. **Minimalfix:** eine Tabellenzelle (oder `destination_of` auf `NotJudgeable` umstellen —
inhaltlich ist es ein Projektseiten-Mangel, also spricht mehr für Exit 1).

### B4 — Der Vertrag behauptet Testdeckung, die es nicht gibt; sechs Verweigerungen der Andockstelle hält kein Test
`docs/office/invoice-app-docking-point.md:189` „**Every sentence above that says ‚refused' or
‚accepted' is held by a test** that runs the shipped script".

Gemessen mit meinem Rig (jede Mutation entfernt genau eine Verweigerung, danach läuft die **ganze**
`tools/test_office_package.py`):

```
g1-category-check-off      rc=0  38 passed     (category_check, :474)
g2-fill-placeholder-off    rc=0  38 passed     (_fill, :428)
g3-plan-rule-count-off     rc=0  38 passed     (destination_of, :442)
g4-pdf-without-xml-off     rc=0  38 passed     (read_document, :182)
g5-range-ambiguity-off     rc=0  38 passed     (range_for, :221)
g6-mixed-rate-off          rc=0  38 passed     (vat_of, :378)
```

Alle sechs funktionieren zur Laufzeit (von Hand gemessen: PDF ohne XML rc 1, zwei Sätze rc 2,
zwei Bereiche rc 2) — es hält sie nur **kein einziger Test**. Vier davon sind wörtliche Sätze des
Vertrags (§1 „A PDF without an embedded XML … is refused", §2 „two ranges match, is refused",
§1/§7 „two VAT rates … refused for booking", §3 „no filing rule for the class").
**Minimalfix:** vier Fälle in die bestehende Parametrisierung; oder der Satz wird auf die Fälle
verengt, die wirklich gemessen sind — beides billig, das erste ist das richtige.

### B5 — AC-4s einziger Red-first-Anker ist ein Test, der für dieses Dokument nicht rot werden kann
`stream-protocol.md` §4, Zeile AC-4: „`tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves`
(green) ist was die Zitate der Tabelle hält."

Gemessen (Rig `ac4-table-pointer`: ein zitierter Testname in `docs/office-kit-from-field.md:150`
durch `test_this_name_resolves_to_nothing_at_all` ersetzt):

```
ac4-table-pointer   rc=0   1 passed in 46.90s
```

Ursache und **Mechanismus** (grösser als AC-4): `tools/test_repo_hygiene.py:1035`
`_CODE_SPAN_RX = re.compile(r"`([^`]+)`", re.DOTALL)` paart Backticks fortlaufend über die ganze
Datei. Ein Zaun (` ``` `, drei Backticks) verschiebt die Paarung um eins; ab dort liest der Leser die
**Lücken** zwischen den Spans. `docs/office-kit-from-field.md` hat seinen ersten Zaun in Zeile 23 —
der Leser findet in der Datei **0** Zitate, obwohl acht dastehen. Über den ganzen Korpus gemessen:
468 geurteilte Zitate, 540 vorhandene Knoten-Ids, **48 Dateien** mit unsichtbaren Zitaten
(u. a. `team-kits/office-team/hooks/gate_ledger_valid.py` 22, `docs/reviews/phase0-disposition.md` 11).
Die Untergrenze `assert judged >= 150` ist global und merkt das Ausfallen ganzer Dateien nicht.

Der Leserdefekt ist **geerbt** (`test_repo_hygiene.py` ist im Paket nicht angefasst) — er gehört als
eigenes Hole-Item durch den Kernel. Was diesem Paket zuzurechnen ist: die Behauptung im Protokoll,
dieser Test halte die neue Tabelle, und dass AC-4 damit ohne Red-first dasteht.

### B6 — `letter_draft.py`: fünf gemessene Tracebacks auf Zahlen, die Nutzer und Projekt schreiben — genau die Klasse D1/D2, die der Strom für geschlossen erklärt
Gemessen (`test_a9_letter_draft_edges`, `test_a9c_…`), jeweils Traceback statt Verweigerung,
obwohl `letter_draft.py:34` sagt „Exit 1 = refused (reason on stderr), nothing written":

| Stelle | Eingabe | Gemessene Zeile |
|---|---|---|
| `letter_draft.py:184` `rate = Decimal(str(args.vat_rate))` | `--vat-rate neunzehn` / `--vat-rate ""` | `decimal.InvalidOperation: [<class 'decimal.ConversionSyntax'>]` |
| `letter_draft.py:228` `date.fromisoformat(args.today)` | `--today gestern` | `ValueError: Invalid isoformat string: 'gestern'` |
| `letter_draft.py:169` `int((terms.get("offer") or {}).get("valid_days") or 14)` | `correspondence.yaml: valid_days: "vierzehn"` | `ValueError: invalid literal for int() with base 10: 'vierzehn'` |
| `letter_draft.py:236` `key=lambda one: int(one.get("level") or 0)` (auch `:245`) | `correspondence.yaml: level: "zwei"` | `ValueError: invalid literal for int() with base 10: 'zwei'` |
| `letter_draft.py:229` `date.fromisoformat(row["doc_date"])` | Ledger-Zeile `02.08.2026` | `ValueError: Invalid isoformat string: '02.08.2026'` |

`correspondence.yaml` ist das Dokument, das der Nutzer über `apply-proposal` **selbst füllt** (D8) —
ein Tippfehler dort endet für einen Nicht-Entwickler im Python-Traceback. Der Strom hat für dieselbe
Klasse in der Schwesterdatei einen benannten Leser gebaut (`invoice_intake.series_number`), in der
Datei, die er in derselben Sitzung neu schrieb, aber nicht. **Minimalfix:** ein Leser wie
`series_number` (Wert, Herkunftsname, Exception) an den fünf Stellen; Test analog
`test_a_series_the_intake_cannot_order_is_refused_and_never_crashes`.

### B7 — „erfindet keinen Term" ist gemessen falsch (Verfassung, Skill, Docstring)
`team-kits/office-team/constitution/AGENTS.md:346` „the script **invents no fee, no term and no
sender**: where the business recorded none it refuses and says which";
`skills/correspondence/SKILL.md:30` „It invents no fee, no term and no address";
`letter_draft.py:24` „the kit invents no 14 days".

Gemessen (`test_a12_the_terms_the_script_fills_when_the_document_carries_none`,
`correspondence.yaml` auf `reminders: []` reduziert, also ohne `address`, `closing`, `offer.valid_days`):

```
offer with no terms at all: rc=0
… Dieses Angebot gilt bis zum 20.09.2026.        (= 14 Tage, letter_draft.py:169 `or 14`)
… Sehr geehrte Damen und Herren,                 (= ADDRESS_FORMS["Sie"], :106 `or "Sie"`)
… zuzüglich 19 % Umsatzsteuer: 19,00 EUR         (= argparse-Default :300)
… Mit freundlichen Grüßen                        (= :195 `or "Mit freundlichen Grüßen"`)
```

Vier vom Kit gewählte Werte stehen im Brief an einen Kunden. BUG-0259 („limits": „The values are
also visible in the document the user owns") deckt diese Code-Fallbacks nicht ab — sie greifen
gerade dann, wenn der Nutzer die Werte aus dem Dokument entfernt. **Minimalfix:** entweder die drei
Terme verpflichtend lesen (Refusal mit Route, wie die Leiter) oder die drei Sätze auf das kürzen,
was gebaut ist — und BUG-0259 um den Code-Fallback erweitern.

---

## 2. Nicht blockierend — benannte Reste (gehören als Hole-Item bzw. in die Nacharbeit)

* **N1 — Zwei Dokumente, ein Ablageziel; die sanktionierte Kette lässt das Überschreiben durch.**
  Gemessen (`test_a11_two_documents_render_one_destination`): zweites Verdict rc 0 mit demselben
  `destination`, danach `_through_the_chain` auf `mv inbox/b.xml <bestehendes Ziel>` → **rc 0**.
  Die vom Entwurf vorgeschlagene `filename_template` (`YYYY-MM-DD_<counterparty>_<doctype>`) trägt
  keine Rechnungsnummer, und mehrere Rechnungen pro Kunde und Tag sind der Normalfall der App.
  Ein Satz Fix: `destination_of` refust ein Ziel, das schon existiert (oder verlangt für
  `issued_by: app`-Klassen ein `<invoice_no>`/`<number>` im Template — die Füllung kann es bereits).
* **N2 — „the first attachment ending in `.xml`"** (`invoice-app-docking-point.md:24`) ist nicht,
  was der Code liefert. Gemessen (`test_a1_…`): PDF mit `factur-x.xml` (zuerst angehängt, korrekte
  Zahlen) und `aaa-invoice.xml` (danach angehängt, 999.00) → akzeptiert **mit 999.00**. Massgeblich
  ist die Namensbaum-Reihenfolge von pypdf, nicht die Anhängereihenfolge. Der zweite Halbsatz der
  Zeile („the PDF pages themselves are never read") ist dagegen gemessen korrekt und die richtige
  Bindung für den XML-vs-Sichttext-Angriff.
* **N3 — `docs/office-kit-from-field.md:161`** „jede Zeile nennt den Test, der es misst" — gemessen
  falsch für F4 (nennt ein Dokument), F5 (nennt eine Datei plus „Block H125"), F7a und F7b (nennen
  gar keinen Test): 4 von 9 Zeilen.
* **N4 — Protokoll §9 ist unvollständig:** das dritte offene Loch dieses Ziels, **BUG-0248 (H166,
  mixed-VAT)**, ist am 2026-09-05 21:58:52 korrekt durch den Kernel erfasst, steht aber nicht in der
  Löcher-Sektion des Protokolls; `invoice_intake.py:57` sagt „filed as a hole item", ohne die Nummer
  zu nennen (Hausregel 4: der Zeiger ist die Nummer).
* **N5 — `series_number` nimmt, was `int()` nimmt.** Gemessen: `'007'`→7, `' 7'`→7, `'1_0'`→**10**,
  `'+7'`→7, `'٧'`→7; `'7.0'` und `''` werden mit Verweigerung abgewiesen, kein Traceback. Kein
  Laufzeitloch (Kollisionen enden in „already booked"), aber Docstring und Vertrag („a decimal
  number", „Zero-padding is fine") sind enger als der Leser.
* **N6 — Mahnung ohne Gegenpartei:** Ledger-Zeile mit leerem `counterparty` → rc 0, Entwurf
  `…_unbekannt_mahnung-2.md` mit leerer Empfängerzeile, während ein fehlender Absender refust wird.
* **N7 — AC-6 „die übrigen Module gegreppt":** ich habe den Grep wiederholt. Gedruckte
  `request-approval`-Zeilen ausserhalb von `documents.py`/`filing.py`: `presets.py:523`,
  `kitupdate.py:1246` (beide vom Manifest-Prädikattest gedeckt), sowie `cli.py:428` und
  `migrate.py:2817`, die **Platzhalter**-Zeilen drucken (`--key <key>`, `<ID>`) und keine
  ausführbaren Zeilen sind. Das ist in Ordnung, steht aber nirgends — ein Satz im Protokoll fehlt.

---

## 3. Ergebnis je Abnahmekriterium

| AC | Urteil | Grundlage |
|---|---|---|
| **AC-1** (Kern, DEC offen) | **FAIL** | Kern gebaut und gemessen: drei Entwürfe aus Ledger + Stammdaten in `outbox/`, Kopfzeile mit Prüf- und Versandpflicht, Humanizer-**Zählhälfte** wirklich gemessen (nicht behauptet), Ladder-Refusal mit Route (`ac1-ladder-refusal-without-route` → rc 1, eigener Nachbau). Fällt an **B6** (Tracebacks) und **B7** (falsche Eigenschaftsbehauptung in Verfassung/Skill/Docstring). `dec-correspondence.json` ist vollständig, beide Optionen mit gemessenen Kosten, Empfehlung und verworfener Alternative — der DEC-Teil wartet zu Recht auf den Nutzer. |
| **AC-2** | **FAIL** | Der gebaute Teil ist stark und gemessen: drei Dateiformen akzeptiert, 14 gepflanzte Verstösse refust, Kontinuität je Geschäft, Ablage über die **registrierte** Hook-Kette, Buchung danach; zwei Geschäfte mit eigenen Bereichen akzeptiert (rc 0), gleiche Muster refust („make the patterns disjoint" — Vertrag §2 sagt es). Fällt an **B1**, **B2**, **B3**, **B4**. |
| **AC-3** | **PASS** | `chart_of_accounts.yaml` mit `active: null`, `legal_space: DE`, Formularjahr = Vokabular; Kernel-Schreiber gemessen (`apply-proposal`, additiv, Pflichtfeld-Verlust refust mit Route, Duplikat-Konto beim **Buchen** refust mit Route); Buchung nennt `account 4930 Bürobedarf (SKR03)`; Report `## Nach Konto` plus gedruckter Zeilen-Widerspruch. Red-first eigenhändig: `ac3-chart-account-unanchored` rc 1, `d6-vendor-name-in-template` rc 1. Kein Befund. |
| **AC-4** | **FAIL** | Tabelle ist da, mit Urteil je Punkt und zwei begründeten Ablehnungen — aber ihr einziger Red-first-Anker kann nicht rot werden (**B5**), und die Schlusszeile behauptet mehr, als die Tabelle trägt (**N3**). |
| **AC-5** | **PASS** | `ac5-bug0070-created-rules` rc 1 (eigener Nachbau); Kategorien-Weg über den Einstiegspunkt gemessen, Altbestand und ausgeliefertes Dokument; Sonderfall-vs-Allgemein steht in `documents.py`. Angriff auf den Schreiber (Duplikat, fehlendes Pflichtfeld, fehlende Freigabe) endet je in einer Verweigerung **mit** ausführbarer Route. |
| **AC-6** | **PASS** | `ac6-bug0079-documents-reason`, `ac6-bug0079-filing-flags`, `ac6-bug0072-reconciliation`, `d5-remedy-flags-second-derivation` — alle vier rc 1 im eigenen Rig; die gedruckten Zeilen werden im Test wirklich ausgeführt und die geprägte Freigabe deckt danach denselben Befehl. Grep der übrigen Module wiederholt (N7). |

## 4. Pflichten 7–9

* **Pflicht 7 (Red-first, Leser-Mutationen, Löcher):** **teilweise FAIL.** 27 Mutationen des
  Umsetzers nachgezählt: 27 Logs, **jedes rc 1** (nachgerechnet, Erstzeile jedes Logs). Eigene
  15 Mutationen gefahren, alle rot ausser den sechs Deckungs-Sonden (§B4), die absichtlich grün
  bleiben mussten und es taten. **Aber:** DEC-0080 (6) verlangt je NEUEM Leser eine Mutation in der
  Richtung, die sein Docstring bestreitet — für `category_check`, `_fill`, `destination_of`,
  `read_document`, die Bereichs-Mehrdeutigkeit in `range_for` und die Mischsatz-Verweigerung in
  `vat_of` gibt es keine (gemessen: alle sechs entfernbar, Suite bleibt grün). Dazu **B5**
  (benannter Test, der nicht scheitern kann). Löcher: BUG-0258/0259 sauber über den Kernel erfasst,
  mit `limits`, `hole_number` und Modulpräfix in den Zitaten; H176 **wirklich geerbt** (gemessen:
  `git show b7f282e:docs/POST_V2_WISHLIST.md` → 0 `### H`-Einträge, Test rot in meiner Kopie:
  „only 0 hole entries found … assert 0 >= 90"); H166 fehlt im Protokoll (N4).
* **Pflicht 8 (Nähte):** **PASS.** `cli.py` nur ein Block, kein neues Subkommando (Diff geprüft);
  `lead_package_sizes.json` einmal auf 58960 gesetzt, das Journal in `phase0-disposition.md` §10
  trägt alle drei Schritte mit Begründung (angehängt, nichts überschrieben); vier
  Verfassungs-Abschnitte neu gepinnt mit `--note`; README eine Zeile; keine dev/research-Datei
  ausser den VERSION-Stempeln (Diff gegen `b7f282e` geprüft).
* **Pflicht 9 (Übergabe):** **PASS.** Patch `stream-office.patch`: 28 Dateien, **keine**
  VERSION-Hunks, keine `project_memory/`-Hunks des Repos, **kein CR**, `git apply --check` gegen
  einen frischen `b7f282e`-Export **rc 0**; nach dem Anwenden sind `tools/` und `docs/` byteweise
  identisch mit dem Paketbaum, `team-kits/` bis auf die drei VERSION-Dateien (und lokalen
  `.ruff_cache`-Müll im Worktree, nicht im Patch). Alle sieben neuen Dateien liegen im Patch.
  Protokoll vollständig bis auf N4/N7. Kein Commit, kein Push, keine Installation gefunden.

## 5. Ausdrücklich gemessene Negativbefunde (Angriff lief, kein Loch)

* VAT-Schreibweisen: Kategorie `'s'` (Kleinschreibung) → refust; `'S '` → akzeptiert; Rate `'19,0'`
  → refust; `' 19 '`, `'19.0000'`, `'1_9'`, `'+19'` → akzeptiert **und** vom Ledger angenommen
  (rc 0) — kein Sackgassen-Paar zwischen Extraktor und Ledger.
* Zwei Geschäfte mit derselben Zählnummer in eigenen Bereichen → akzeptiert (rc 0); gleiche Muster →
  rc 2 mit „make the patterns disjoint", und der Vertrag §2 sagt genau das.
* XRechnung/UBL mit einem Verstoss ausserhalb der Teilmenge (keine BG-23) → akzeptiert; das ist die
  dokumentierte Grenze (§7) — der Schaden daran ist B1, nicht die Grenze selbst.
* ZUGFeRD-PDF: Sichttext wird nie gelesen, das XML gewinnt — genau wie dokumentiert (N2 betrifft nur
  die Auswahl zwischen zwei XML-Anhängen).
* Kernel-Schreiber: Duplikat-Konto → Schreiber nimmt an (Addition), **Buchung** refust mit Route;
  Pflichtfeld entfernt → `request-approval` refust mit Route; ohne Freigabe → refust mit
  ausführbarer Route.
* Direkte Ledger-Bearbeitung auf eine nicht gemappte Kategorie: der Report zeigt sie unter
  „ohne Konto" mit erklärendem Satz — die beiden Ledger-Regeln (D9) widersprechen sich nicht.
* `ruff check .` im Paketbaum: nur zwei Funde, beide in **meiner** Angriffsdatei; Paket sauber.
* `tools/test_office_package.py` in meiner Kopie: **38 passed in 50.41s**.

## 6. Nicht gemessen (bewusst offen gelassen)

* Die vollen Reichweiten-Suiten des Umsetzers (`test_hooks.py`, `test_e2e.py`,
  `test_research_chain.py`, die 533er Kernel-Gruppe, der 2304er Lauf) — Hostregel, ein Pytest zur
  Zeit, und das Nachfahren eines protokollierten Laufs ist nicht meine Aufgabe. Die dev/research-
  Regressionsfreiheit ist damit **unbestätigt**, nicht widerlegt.
* `tools/validate.py`, `bump_kit_version.py` (Stempel ist provisorisch, gehört zum Merge).
* Der Zeit- und Tokenverbrauch des Umsetzers (§10 des Protokolls) ist von hier nicht prüfbar.
* Die Humanizer-Hälfte, die kein Zähler misst (ob ein Mensch den Brief als menschlich liest) — sie
  ist als Pflicht benannt und das ist die richtige Behandlung.

## 7. Uhr

Start der Prüfung **2026-09-06 00:04:08**, Ende der Messungen **2026-09-06 00:35:43** (Uhr gelesen nach der letzten Messung); alle Zeiten gelesen, keine hochgerechnet.

---

**Verdikt: FAIL.** B1, B2, B3, B4, B5, B6, B7 blockieren die Runde. N1 gehört als Hole-Item mit
Messung erfasst (oder mit dem Einzeiler geschlossen), N2–N7 sind Nacharbeit im selben Paket.
Der Leser-Defekt hinter B5 (`_CODE_SPAN_RX`) ist geerbt und gehört als eigenes BUG-Item durch den
Kernel — er entwertet die Zeiger-Prüfung für 48 Dateien des Repos, nicht nur für dieses Paket.
