# TSK-0132 (PR-0009, G5-3 Office) — Prüfbericht Runde 3 (Abschluss)

Rolle: `harness-verifier`. Frische Kopie ausserhalb des Repos:
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0132/verify/tree3` (Spiegel von `g5-office` ohne
`.git`), frischer Basisexport `…/verify/base3` (`git archive b7f282e`). Eigenes Rig
`…/verify/rig3.py` — verweigert ausserhalb seines Verzeichnisses (DEC-0070), binär, SHA-256-Kontrolle
nach jedem Lauf. Uhr: Start **2026-09-06 09:21:14**, Ende **09:37:06**.
Baseline in meiner Kopie: `tools/test_office_package.py` **70 passed in 80.19s**.

**Urteil: PASS.** R1–R7 sind gemessen geschlossen; kein blockierender Befund bleibt. Zwei benannte,
nicht blockierende Reste stehen unten.

---

## 1. R1–R7, je gemessen

### R1 — der argparse-Default `19` (blockierend in Runde 2) — **PASS**
`letter_draft.py:423` `default=""`. Gemessen (`test_r1_offer_without_the_flag`), beide Formen:

```
offer WITHOUT --vat-rate:  rc=1  [letter_draft] REFUSED: this business is not a Kleinunternehmer
   (business_profile.yaml `tax.kleinunternehmer`), so an offer states a VAT rate and this script
   invents none. Remedy: `--vat-rate 19` (or the rate that applies to this service).
   drafts: []
offer with --vat-rate '':  rc=1  (dieselbe Verweigerung)
```
Mutation `v3-r1-vat-default` (Default wieder `"19"`) → **rc 1**, der benannte Test wird rot. Die
Docstring-Stelle (`letter_draft.py:22-39`) trägt die Korrektur ausdrücklich („The FOURTH default …
survived the first repair while three texts said it had not").

### R2 — ein numerischer Leser statt zweier ungleicher — **PASS** (ein Rest, §2)
Gemessen (`test_r2_a_number`, `test_r2b_the_other_numeric_sites`):

```
--vat-rate 'NaN'       rc=1  … is 'NaN', which is not a finite number and cannot stand in a letter
--vat-rate 'Infinity'  rc=1  … not a finite number …
--vat-rate '-19'       rc=1  … this script writes no negative --vat-rate into a letter to a customer
--vat-rate '19,0'      rc=0  'zuzüglich 19 % Umsatzsteuer: 19,00 EUR'
--vat-rate '1e2'       rc=0  'zuzüglich 100 % Umsatzsteuer: 100,00 EUR'      (R7)
fee NaN                rc=1  fee is 'NaN', which is not a finite number …
fee -5                 rc=1  … writes no negative fee …
level 1.5              rc=1  … needs a whole number there
days_after_due -3      rc=1  … writes no negative … into a letter to a customer
valid_days 2.5         rc=1  correspondence.yaml `valid_days` is '2.5' … whole number
```
Kein Traceback in irgendeinem Fall. Mutationen `v3-r2-finite` → rc 1 (2 failed),
`v3-r2-sign` → rc 1.

### R3 — `EINVOICE_ROOTS`: „ist eine E-Rechnung" statt „parst als XML" — **PASS**
Gemessen (`test_r3_attachment_selection`) an PDFs, die ich selbst gebaut habe:

```
note beside the invoice (aaa-note.xml + factur-x.xml):  rc=0   net=214.20 gross=254.90
two real invoices (aaa-invoice.xml + factur-x.xml):     rc=1   [einvoice] this PDF carries 2
        embedded e-invoice XML files (aaa-invoice.xml, factur-x.xml) … refused
```
Der Notiz-Anhang wird nicht mehr mitgezählt, die echten Zahlen kommen aus `factur-x.xml`; zwei
echte Rechnungen werden weiter mit beiden Namen verweigert. Mutation `v3-r3-einvoice-roots`
(`return tag` ohne die Menge) → **rc 1**. Die Definition steht einmal (`einvoice_extract.py:54`) und
wird von `parse_xml` und `_is_an_einvoice` gelesen.

### R4 — die gedruckte Zeile — **PASS**, und meine Runde-2-Empfehlung war falsch
Gemessen (`test_r4_printed_line_round_trip`):

```
buyer '--doc-type'      PRINTED: … "--counterparty=--doc-type" …   ROUNDTRIP OK: True
                        --book rc=0   LEDGER: …,income,invoice,--doc-type,RE-2026-0004,…
buyer 'He said "hi"'    PRINTED: (keine Zeile) "this document carries a value no command line can be
                        retyped with … Run `python scripts/invoice_intake.py … --book`"
                        --book rc=0   LEDGER: …,"He said ""hi""",…   (exakt der Name, CSV-verdoppelt)
buyer 'Zwei  Leerzeichen'  ROUNDTRIP OK: True, --book rc=0
```
**Eigener Fehler aus Runde 2, ausdrücklich:** ich hatte
`kernel.documents.quoted_for_a_command_line` als fertige Definition empfohlen. Gemessen an der
laufenden Funktion:

```
quoted_for_a_command_line('He said "hi"') -> "He said 'hi'"
```
Sie tauscht das innere Anführungszeichen — richtig für einen Freitext-Grund, falsch für einen Wert,
der **gebucht** wird: der Kunde hätte als `He said 'hi'` im Ledger gestanden. Die gewählte Lösung
(rendern, POSIX-zurücksplitten, nur bei Gleichheit anbieten, sonst `--book` nennen) ist die
richtigere, und der Docstring sagt ausdrücklich, dass der Rundlauf der POSIX-Rundlauf ist und über
PowerShell nichts behauptet wird. Mutation `v3-r4-round-trip` (Zeile immer anbieten) → **rc 1**.
(Meine Mutation `v3-r4-flag-equals` erzeugte ungültiges Python — mein Fehler, rc 2, kein Befund;
die `--flag=value`-Form ist über den Rundlauf-Test mitgemessen.)

### R5 — zwei Plan-Regeln für eine Klasse — **PASS**
```
two plan rules -> rc=1  [intake] NOT JUDGEABLE …: 2 plan rule(s) file the class 'sales_invoice' …
   exactly one is needed. Remedy: two rules for one class make the destination a guess, and this
   kernel never edits or removes a rule … give one of them its own class …
```
Die Remedy folgt jetzt der Zahl. Mutation `v3-r5-plan-rule-count` (`!= 1` → `< 1`) → **rc 1** (in
Runde 2 blieb dieselbe Mutation grün).

### R6 — die Zahlen von BUG-0263 — **PASS**
Das Item trägt beide Konventionen nebeneinander (486/525/39 mit geleerten Zaunblöcken;
475/529/54 mit ganz ausgeschlossenen — meine Runde-2-Zählung, korrekt zugeordnet), den Satz, dass
keine der Paare exakt ist, und ein neues **AC-5**, das den Schliessenden zwingt, einmal zu zählen
und die Konvention zu nennen.

### R7 — `1e2` im Kundenbrief — **PASS**
`plain()` rendert `100 %` statt `1E+2 %` (gemessen oben); Mutation `v3-r7-plain` → **rc 1**.

---

## 2. Nicht blockierende Reste

* **V3-1 — eine Leser-Richtung ohne Fall (DEC-0080 (6)).** `a_count`s Docstring sagt „A whole,
  non-negative number"; meine Mutation `v3-r2-count-whole` (die Ganzzahl-Prüfung entfernt) lässt
  **alle 70 Tests grün**, während die Verweigerung zur Laufzeit funktioniert (gemessen:
  `level 1.5` und `valid_days 2.5` je rc 1). Es fehlt der Fall, nicht der Code — dieselbe Form wie
  R5 in Runde 2, eine Ebene tiefer.
* **V3-2 — Kosmetik im Kundenbrief.** Der Satz „zuzüglich **19.5** % Umsatzsteuer" schreibt den
  Steuersatz mit Dezimalpunkt, während jede Geldzahl derselben Zeile deutsch gesetzt ist
  („19,50 EUR"). Betrifft nur nicht ganzzahlige Sätze.
* **V3-3 — ein Zeiger, der schmaler geworden ist.** `skills/correspondence/SKILL.md:32-33` belegt
  „a value it cannot read is a refusal and never a traceback" weiter nur mit
  `::test_a_value_letter_draft_cannot_read_is_refused_and_never_crashes`; die andere Hälfte (nicht
  endlich, negativ) hält seit R2 `::test_a_number_letter_draft_cannot_write_into_a_letter_is_refused`.
  Der genannte Test existiert und hält einen Teil — kein toter Zeiger, nur ein zu schmaler.

---

## 3. Was ich sonst nachgerechnet habe

* **Patch:** 28 Dateien, **0 CR-Bytes**, keine VERSION-, keine repo-`project_memory`-Hunks;
  `git apply --check` gegen einen frischen `b7f282e`-Export **rc 0**; nach dem Anwenden ist der
  Baum byte-identisch mit dem Paket bis auf die drei VERSION-Dateien (und die Laufzeit-Datei
  `project_memory/.audit/hook_events.jsonl` des Worktrees, die der Patch zu Recht nicht trägt).
* **Die 118 wiederhergestellten Zeilen:** `test_add_filing_rule_creates_the_rules_list_on_an_old_stock_plan_through_the_entry_point`
  (`:289`), `LEDGER_HEADER` (`:398`), `PILOT_PROFILE` (`:400`), `PILOT_PLAN` (`:413`),
  `income_row` (`:422`), `pilot_project` (`:428`) — alle vorhanden, Suite 70 passed. Das Protokoll
  meldet den Werkzeugfehler selbst und nennt die Regel, die er brach.
* **Rig:** 51 `redfirst-*.log`, **jedes rc 1**; 51 deklarierte Mutationen, keine ohne Log und kein
  Log ohne Deklaration (nachgezählt).
* **Die zwei roten Tests gehören nicht dem Paket:** gegen den Hauptspeicher gerechnet
  (**84 Entscheidungen, 322 Zeiger, 0 unaufgelöst**) ist die DEC-Naht grün — der Worktree-Rot liegt
  nur an dessen `b7f282e`-Stand von `project_memory/`; und `git show b7f282e:docs/POST_V2_WISHLIST.md`
  trägt **0** `### H`-Einträge (H176 geerbt).
* **Office-Stempel** `2026.09.06-3`, provisorisch — der endgültige gehört zum Merge.

---

## 4. Abschlussurteil TSK-0132

| Kriterium | Urteil | Grundlage |
|---|---|---|
| **AC-1** (FR-0033 unter DEC-0082) | **PASS** | Workflow ohne Rollen-Verdrahtung; drei Entwürfe aus Ledger + Stammdaten mit der Prüfpflicht in der ersten Zeile; Humanizer-Zählhälfte auf den **gerenderten** Texten gemessen (Runde 2: Mutation im Text → rot); jeder Term und jede Zahl gelesen oder verweigert (R1, R2); die zwei Grenzen aus DEC-0082 (3) stehen in drei Texten |
| **AC-2** (Andockstelle, DEC-0075) | **PASS** | Aufnahme, Norm-Teilmenge, Dreiklang, Kontinuität je Geschäft, Ablage über die registrierte Kette, Buchung; Exit-Code-Definition auf sechs Sonden bestätigt; die Buchungszeile wird vom Ledger selbst geprüft und nur angeboten, wenn der POSIX-Rundlauf sie trägt (R4); Anhangwahl als Eigenschaft (R3); zwei Regeln, ein Ziel, eine Nummer — je verweigert (R5, N1, N5) |
| **AC-3** (FR-0081) | **PASS** | Runde 1 gemessen, unverändert |
| **AC-4** (FR-0002) | **PASS** | Urteilstabelle mit Test bzw. Item je Zeile; der Schlussabsatz sagt genau, was sie trägt; der Anker geht rot, die repo-weite Prüfung als Kontrolle grün (BUG-0263) |
| **AC-5** (BUG-0070 + BUG-0071) | **PASS** | Runde 1 gemessen; beide waren vor diesem Strom gebaut, die Messung durch den Einstiegspunkt ist neu und rot-erst |
| **AC-6** (BUG-0072 + BUG-0079) | **PASS** | Remedies werden ausgeführt und angenommen; die Anhangwahl (BUG-0072-Klasse über einen Dateinamen) ist mit R3 geschlossen |
| **Pflicht 7** (rot-erst, Leser-Mutationen, Löcher) | **PASS** mit einem Rest | 51 Mutationen rc 1 nachgezählt; ich habe in drei Runden 35 eigene gefahren; offen bleibt V3-1 (eine Richtung ohne Fall). Löcher: BUG-0248 (H166), BUG-0258 (H176), BUG-0259 (H177), BUG-0263 (H181) — alle über den Kernel erfasst, mit `limits` und Modulpräfix |
| **Pflicht 8** (Nähte) | **PASS** | `cli.py` ein Block ohne Subkommando; Grössenjournal und Abschnitts-Pins angehängt statt überschrieben; keine dev/research-Schreibung ausser den VERSION-Stempeln; die DEC-0082-Naht nachgerechnet |
| **Pflicht 9** (Übergabe) | **PASS** | Patch, Protokoll (mit §0- und §11-Selbstkorrekturen), Rig, Stempel, Scratch-Ort; kein Commit, kein Push, keine Installation |

**Nicht gemessen (unverändert):** die grossen Lesesuiten des Umsetzers (3399 passed / 562 passed +
2 erklärte Rote) habe ich nicht wiederholt — Hostregel und Rollenteilung; nachgerechnet habe ich
die Erklärungen beider Roten, die Log-Bilanz und jede Behauptung, die ich selbst prüfen konnte.
`tools/validate.py` und `bump_kit_version.py` gehören zum Merge.

---

**Verdikt: PASS.** Die vier Blocker der Runde 2 sind gemessen geschlossen, die drei Notizen
ebenfalls; V3-1 bis V3-3 sind benannte, nicht blockierende Reste für den Merge oder die nächste
Runde. Für R4 halte ich fest, dass meine eigene Empfehlung aus Runde 2 falsch gewesen wäre und die
gewählte Lösung besser ist — gemessen an der Funktion, die ich empfohlen hatte.
