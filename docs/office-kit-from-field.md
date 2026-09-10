# Was das Office-Kit aus einem echten Betrieb übernehmen sollte

Gemessen am 2026-08-04 an der Kopie von BuyPlugGo (`v2-pilot/BuyPlugGo-KOPIE`, Kit
`2026.07.17-8`, vier Wochen Betrieb, 16 Verfahren, ein Aktenplan über 920 abgelegte Dokumente).
Das Original ist ein laufendes Geschäft und wurde nicht angefasst.

Die Trennlinie dieses Dokuments: **generalisierbar ist, was jeder deutsche Kleinbetrieb braucht.
Spezifisch ist, was BuyPlugGo als Händler braucht.** eBay-, Kaufland- und Shopify-Abläufe, der
Produktkatalog, die Preislisten und die Bildpflege stehen deshalb NICHT auf dieser Liste, so gut
sie im Feld auch funktionieren.

---

## F1 — Der Aktenplan wird gefüllt ausgeliefert (höchster Wert)

**Heute:** das Kit liefert `filing_plan.yaml` mit einer leeren Regelliste aus. `gate_filing`
schlägt darauf fail-closed an — **das erste Dokument, das ein frisch aufgesetztes Office-Projekt
je ablegen will, wird verweigert.** Und weil es ein Kit-Dokument ist, hat es nach der Installation
keinen Schreiber mehr: wer es nicht beim Aufsetzen füllt, kommt nicht mehr heran.

**Aus dem Feld:** BuyPlugGos Baum ist kein Sonderweg, sondern der deutsche Normalfall —

```
archive/1-Finanzen/Rechnungen/<Jahr>/1_Eingangsrechnungen/<Quartal>/<MM>/
archive/1-Finanzen/Rechnungen/<Jahr>/2_Ausgangsrechnungen/<Quartal>/<MM>/
```

mit Dokumentklassen je Knoten (`invoice_incoming`, `credit_note`, `cancellation_storno`,
`purchase_receipt_kaufbeleg`, `differenzbesteuert`, `shipping_receipt`).

**Zu übernehmen:** ein gefüllter DE-Standardaktenplan als Vorlage, den ein Projekt kürzt statt ihn
zu erfinden. Ein Kit, dessen Kernfunktion beim ersten Gebrauch verweigert, ist kein Kit.

## F2 — Aufbewahrung ist ein Feld mit Rechtsgrundlage und einem Ehrlichkeitsvermerk

**Aus dem Feld,** wörtlich je Knoten:

> `retention: "8y (Belege gem. Paragraph 147 AO — DE-Default; confirm with Steuerberater)"`

und im Kopf der Datei der Vermerk, dass diese Vorgaben **nicht** gegen die tatsächliche Beratung
geprüft sind.

**Zu übernehmen:** beides. Die Frist mit ihrer Rechtsgrundlage — und der Vermerk, dass ein
Standardwert ein Standardwert ist. Das ist im Aktenplan dieselbe Hausregel wie im Code: kein
Kommentar darf Schutz behaupten, den niemand gebaut hat.

## F3 — Benennung als Schema, nicht als Gewohnheit

**Aus dem Feld:** `naming_rule: "YYYY-MM-DD_<counterparty>_<doctype>"`, dazu eine Tabelle je
Dokumentart für die Fälle, die davon abweichen.

**Zu übernehmen:** die Regel als Vorlagenfeld mit der Tabelle daneben. Ohne sie entscheidet jeder
Ablauf neu, wie eine Datei heißt, und nach hundert Dokumenten ist der Bestand unsortierbar.

## F4 — Die Grenze zwischen Eingang und Archiv, als Definition

Das ist die teuerste Erkenntnis im ganzen Repo, weil sie über mehrere Fassungen erarbeitet wurde
(v1.2 → v1.9):

> Der **Eingang** liegt im Wurzelverzeichnis neben dem Archiv, nicht darin, und hat **keine
> Unterordner**. Unklare Fälle wandern nicht in einen Eingangs-Unterordner, sondern in einen Knoten
> **innerhalb** des Archivs (`archive/0-Prüfen/`).

**Der Grund ist mechanisch:** Bewegungen innerhalb des Archivs sind vom Wächter erlaubt. Liegt der
Klärungsknoten im Eingang, muss ein Mensch jede unklare Datei von Hand hinübertragen — ein
Zwischenschritt, den die erste Fassung hatte und der im Betrieb nicht durchgehalten wurde.

**Zu übernehmen:** als Definition in die Vorlage, mit dem Grund. Ein Kit, das nur die Struktur
liefert, lässt jeden Betrieb dieselben zwei Fassungen durchlaufen.

## F5 — Gelöscht wird nie; es gibt eine Quarantäne

**Aus dem Feld** (PROC-0015 und der Aktenplan):

> Dateien, die als überholt oder kaputt erkannt werden, wandern mit **protokolliertem Grund** in
> einen Quarantäneknoten. Das Team löscht nicht. Nur die Inhaberin leert ihn.

**Zu übernehmen:** wörtlich. Bei Geschäftsdokumenten ist ein irrtümliches Löschen nicht
reparierbar, und ein Agent, der löschen darf, wird es irgendwann tun.

## F6 — Zwei Dinge in `.gitignore`, beide aus Schaden gelernt

**(a) Die Unterscheidung, welche Geschäftsdaten versioniert werden.** Aus dem Feld:

> Binäre Dokumente werden **nicht** verfolgt — sie blähen das Repo, und die DSGVO-Löschung nach
> Art. 17 muss möglich bleiben, denn Git-Historie ist für immer. **Das Ledger bleibt verfolgt:**
> die gesetzliche Aufbewahrung geht der Löschung vor.

Diese Abwägung ist richtig und trifft jeden Betrieb, der Belege und Buchhaltung im selben Repo
hält. Sie gehört ins Kit, nicht in jedes Projekt neu.

**(b) Eine gemessene Falle:** `dir/` schließt das Verzeichnis aus, und Git kann eine Datei darin
danach **nicht** wieder einschließen. Damit waren die Ordner-Seeds des Kits still unverfolgt und
ein frischer Klon kaputt. Richtig ist `dir/*` plus Negation.

**Zu übernehmen:** beides, mit der Begründung — sonst „vereinfacht" die nächste Hand es zurück.

## F7 — Zwei wiederkehrende Verfahren sind Büroarbeit, nicht Handel

Von den 16 Verfahren sind die meisten händlerspezifisch. Diese zwei nicht:

- **Eingangsroutine** (PROC-0005): eine Schleife je Datei — öffnen, klassifizieren, umbenennen,
  buchen / zur Klärung parken / in Quarantäne. Das ist der Kernablauf jedes Büros.
- **Unabhängige Projektprüfung** (PROC-0010): eine wiederkehrende, **read-only** Stichprobe über
  Ablage, Ledger und Berichte, die gegen die Quellen reproduziert. Im Feld hat sie 435 von 435
  Quellen byte-identisch bestätigt und dabei zwei Hygienemängel gefunden, die sonst niemand
  gesehen hätte.

**Zu übernehmen:** beide als Verfahrensvorlagen. Besonders die Prüfung — ein Kit, das seine eigene
Arbeit stichprobenweise gegen die Quellen prüft, findet Drift, bevor sie teuer wird.

## F8 — Die Jahresansicht

`dashboards/yearly_overview.html` aus PROC-0014: eine interaktive Jahresübersicht über Einnahmen
und Ausgaben aus dem Ledger. Die Zahlen erzeugt `euer_report.py` bereits; **es fehlt die Sicht.**

Deckt sich mit Abschnitt 5 der Wunschliste (Nachtrag des Users vom 2026-07-31) und mit derselben
Bedingung: die Ansicht gehört nach `generated/`, regenerierbar und **nicht committet** — eine
committete Bilanz wäre eine zweite Wahrheit neben dem Ledger, und das Ledger ist der Beleg. Und
sie muss ihre Quelle und ihren Stichtag nennen.

---

## Stand (2026-09-02, TSK-0107 -- Generation 2, Strom G)

Der Stand gehoert in dieses Dokument, weil die Prosa hier liegt und `FR-0002` nur den Zustand
traegt. Was gebaut ist, ist gegen den ausgelieferten Baum gemessen; jede Zeile nennt die Stelle,
nicht den Satz.

| Punkt | Stand | Wo |
|---|---|---|
| F1 | **gebaut** (FR-0031 / TSK-0102) | der Aktenplan wird mit Regelentwurf statt leer uebergeben |
| F2 | **gebaut** | `filing_plan.yaml`: `retention` traegt Spanne UND Rechtsgrundlage, dazu der Ehrlichkeitsvermerk (kein primaerer Gesetzestext gelesen). Der Waechter darauf ist `_duties.retention_duties` |
| F3 | **gebaut** | `filing_plan.yaml`: `filename_template` als Schema mit den drei benannten Abweichungen |
| F4 | **gebaut** | `filing_plan.yaml`: Eingang neben dem Archiv, Klaerungsknoten INNERHALB (`archive/_unsorted/`), plus die Regel `FP-900` im Beispielblock |
| F5 | **gebaut** | `filing_plan.yaml`: Quarantaeneknoten `archive/_quarantine/` plus Regel `FP-901`; die Wand darunter ist der vorhandene `guard_fs_tripwire` |
| F6 | **war schon ausgeliefert, jetzt gemessen** | `templates/repo/.gitignore` trug beide Haelften bereits; neu ist der Stolperdraht `tools/test_hooks_v2.py::test_the_office_gitignore_still_lets_the_tray_seeds_into_a_fresh_clone`, der die `dir/*`-plus-Negation-Falle mit `git check-ignore` in beide Richtungen misst |
| F7 | **offen, eigenes Paket** | zwei Verfahrensvorlagen (Eingangsroutine, unabhaengige Projektpruefung). Braucht PROC-Vorlagen im Kit und einen Rollentext, der sie nennt -- beides ausserhalb von TSK-0107 |
| F8 | **offen, eigenes Paket** | die Jahresansicht. Liegt beim Dashboard-Strom, nicht bei der Vorlagenarbeit; die Bedingung aus Abschnitt 5 der Wunschliste gilt weiter (nach `generated/`, nicht committet, Quelle und Stichtag genannt) |

## Urteil je Punkt (2026-09-05, TSK-0132 -- Generation 5, PR-0009 AC-4)

`PR-0009` AC-4 verlangt fuer jeden der acht Punkte ein Urteil: **gebaut** mit eigener Abnahmezeile,
**aufgenommen** von einem benannten Item, oder **abgelehnt** mit Grund -- keiner bleibt Prosa ohne
Urteil. Die Tabelle oben traegt den Stand von Generation 2; diese traegt das Urteil, gemessen am
Baum von `b7f282e` plus dem Strom `g5/office`.

| Punkt | Urteil | Item / Stelle | Abnahmezeile bzw. Grund |
|---|---|---|---|
| F1 | **gebaut** | FR-0031 / TSK-0102 | `tools/test_hooks.py::test_a_fresh_office_project_files_its_first_document_without_the_user_editing_yaml` -- ein frisches Projekt legt sein erstes Dokument ab, ohne dass der Nutzer YAML tippt; seit TSK-0132 auch auf einem Altbestand ohne `rules:`-Schluessel ueber den Einstiegspunkt (`tools/test_office_package.py::test_add_filing_rule_creates_the_rules_list_on_an_old_stock_plan_through_the_entry_point`, BUG-0070) |
| F2 | **gebaut** | TSK-0107 (FR-0002), TSK-0116 (F6) | `retention` traegt Spanne und Rechtsgrundlage, der Kopf den Ehrlichkeitsvermerk; eine Spanne, die der Fristenleser nicht zaehlen kann, wird beim Schreiben verweigert (`tools/test_kernel.py::test_a_retention_the_deadline_register_cannot_read_is_refused_before_it_reaches_the_plan`) |
| F3 | **gebaut** | TSK-0107 | `filename_template` je Regel, drei benannte Abweichungen im Kopf; der Entwurf (`filing_plan.py --draft`) traegt die Vorlage in jede vorgeschlagene Regel (`tools/test_hooks.py::test_the_filing_plan_draft_derives_one_rule_per_class_the_owner_named`) |
| F4 | **gebaut** | TSK-0107 | Eingang neben dem Archiv ohne Unterordner, Klaerungsknoten innerhalb (`archive/_unsorted/`), als Definition mit Grund im Plan-Kopf; die Andockstelle der Rechnungs-App liest flach aus `inbox/` und legt nach dem Plan ab -- gemessen von `tools/test_office_package.py::test_the_docking_point_files_through_the_registered_chain_and_books` (Ablauf ueber die registrierte Kette) und `::test_two_documents_never_render_one_filing_destination` (zwei Dokumente, ein Ziel: verweigert) |
| F5 | **gebaut** | TSK-0107, TSK-0116 (H125) | Quarantaeneknoten `archive/_quarantine/` als Regel `FP-901`; die Wand darunter ist `guard_fs_tripwire`, dessen Reichweite seit TSK-0116/TSK-0120 die Klassen "genannt / Vorfahre / cd" deckt (`tools/test_hooks.py::test_fs_tripwire_blocks_archive_delete`, `::test_fs_tripwire_blocks_move_out_of_archive`, `::test_fs_tripwire_reads_a_source_deleting_copier_as_a_move_out_of_the_archive`) |
| F6 | **gebaut (gemessen)** | TSK-0107 | `tools/test_hooks_v2.py::test_the_office_gitignore_still_lets_the_tray_seeds_into_a_fresh_clone` misst die `dir/*`-plus-Negation-Falle mit `git check-ignore` in beide Richtungen; die GDPR-Abwaegung steht im `.gitignore` der Vorlage |
| F7a Eingangsroutine | **aufgenommen** | FR-0049 / TSK-0078, Verfassung §2.5 | Die Schleife "oeffnen, klassifizieren, umbenennen, buchen / parken / Quarantaene" ist die REVIEWED PIPELINE der Verfassung (Clerk schlaegt vor, Reviewer urteilt, zwei Lesungen, `gate_filing` + `gate_second_reading`) und nicht eine PROC-Vorlage. **Eine ausgelieferte PROC-YAML-Vorlage ist abgelehnt:** der Kernel erzeugt PROCs je Projekt (`capture PROC`), und eine Datei neben den Items waere eine zweite Autoritaet, die niemand liest -- derselbe Grund, aus dem BUG-0075 eine Datei neben einem Kit-Dokument verwirft |
| F7b Unabhaengige Projektpruefung | **aufgenommen** | die Rolle `project-auditor` (Verfassung §5, Preset `core`) | Wiederkehrende, read-only Stichprobe ueber Ablage, Ledger und Berichte gegen die Quellen, ein Evidence-Item (`kind: audit`) je Lauf -- als ROLLE gebaut statt als PROC-Vorlage; ihre Dispatch-Route ist als `H111` benannt und nicht walkable, das ist der offene Rest und steht dort, nicht hier |
| F8 Jahresansicht | **aufgenommen** | FR-0032 / TSK-0116 (`tools/finance_dashboard.py` -> `dashboards/finanzen.html`) | Einnahmen und Ausgaben des Jahres, offene Posten, EUeR je Quartal, § 19-Wache aus dem Ledger; die Bedingung aus Abschnitt 5 gilt gemessen: nicht committet (`.gitignore`: `dashboards/*` mit Negation fuer `ABOUT.txt`, `tools/test_hooks_v2.py::test_the_office_gitignore_keeps_the_generated_dashboard_out_of_git`), Quelle und Stichtag im Kopf der Seite (`tools/test_finance_dashboard.py::test_the_dashboard_and_euer_report_agree_on_every_quarter`). **Abgelehnt** bleibt eine zweite Seite `yearly_overview.html` neben ihr: zwei Renderer ueber ein Ledger sind die zweite Wahrheit, die Abschnitt 5 ausschliesst |

Was dieser Strom (TSK-0132) selbst zu den acht Punkten baute, ist nur die Andockstelle an F4 und der
Altbestandsfall an F1; alles andere ist Urteil ueber Gebautes.

**Was die Tabelle traegt und was nicht**, weil der Satz davor bis 2026-09-06 mehr behauptete als sie
haelt (Pruefrunde 1, N3): die sechs **gebauten** Punkte nennen je einen Test, und dass jeder dieser
Namen aufloest, misst
`tools/test_office_package.py::test_every_test_the_field_report_verdicts_name_is_one_that_exists`
-- **nicht** der repo-weite Zeiger-Test, der diese Datei ab ihrem ersten Code-Zaun nicht mehr liest
(`BUG-0263` / `H181`, mit der Messung). Die drei **aufgenommenen** Punkte (F7a, F7b, F8) nennen
kein Testverfahren fuer sich selbst, sondern das Item, das sie traegt: ihre Messung liegt dort, und
F7b nennt zusaetzlich `H111` als den offenen Rest. Die beiden **Ablehnungen** (eine ausgelieferte
PROC-Vorlage, eine zweite Jahresseite) tragen einen Grund und keinen Test, weil nichts gebaut wurde.

## Reihenfolge

**F1 zuerst und allein blockierend** — solange der Aktenplan leer ausgeliefert wird, verweigert
jedes neue Office-Projekt seine erste Ablage, und nach der Installation kann es niemand mehr
reparieren. F2 bis F6 sind Vorlagen- und Textarbeit im selben Zug. F7 und F8 sind eigene Pakete.

## Was NICHT übernommen wird

Marktplatz-Abläufe (eBay-Bündelaufteilung, Kaufland-Rechnungsgenerator), Produktkatalog,
Preislisten-Abgleich, Bildpflege, Marketingplan. Sie funktionieren im Feld, aber sie beschreiben
einen Händler, kein Büro. Ein Kit, das sie mitliefert, zwingt jedem Steuerberaterbüro einen
Produktkatalog auf.
