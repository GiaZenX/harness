# Nach V2: gewünschte Erweiterungen (Stand 2026-07-27)

Erfasst nach dem Umbau auf V2, **nicht** Teil der Stufen II.11/0–5. Reihenfolge ist Wunsch, nicht
Beschluss. Jeder Punkt braucht vor der Umsetzung eine eigene Entscheidung; hier steht, was gewollt
ist und was daran offen ist.

## 1. Skills der Rollen gegen anerkannte Standards härten

Anlass: Frontends sehen „KI-generiert und lieblos" aus. Das ist am UI messbar und beim Backend und
der Architektur vermutlich genauso wahr, nur schwerer zu sehen. Die Antwort ist nicht mehr Prozess,
sondern **externe Qualitätsanker**, an denen eine Rolle sich prüfen lassen muss.

Betroffen: `product-designer`, `frontend-developer`, `software-architect`, `backend-developer`,
`quality-engineer`, `project-manager` (dev-team), analog die Pendants in research/office.

Recherche läuft (2026-07-27, ein Agent je Rolle). Vorbefund aus einer Codex-Recherche, **die den
V1-Stand analysiert hat** — ihre Dateipfade (`system_requirements.yaml`, `design.yaml`,
`architecture.yaml`) existieren seit dem Lockstep nicht mehr; die genannten Standards gelten
unabhängig davon:

- Design/Frontend: WCAG 2.2, WAI-ARIA Authoring Practices, Nielsen-Heuristiken, Atomic Design,
  Design-Tokens mit Semantik statt Hex-Werten, Storybook als Komponentenvertrag, Testing-Library-
  Queries (Rolle/Label statt Implementierungsdetail), Playwright für kritische Flüsse, Core Web
  Vitals als Akzeptanzkriterium, Loading/Empty/Error als Pflicht-Zustandsmatrix je View.
- Backend/Architektur: OpenAPI-first, Contract-Tests (Pact), Clean Architecture/SOLID als
  Leitplanke, Threat Modeling + OWASP ASVS, OpenTelemetry ab Servicegrenze, Testpyramide statt
  Unit-only, Migrations-/Rollback-Disziplin.
- Betrieb/Steuerung: Branch Protection, CODEOWNERS, CodeQL, Dependency Review, SBOM/SLSA, SLOs mit
  Fehlerbudget, DORA-Metriken.
- Research: FAIR-Prinzipien, Datenversionierung, Reproduzierbarkeitspfade.

Offen: welche davon als **Regel** (INV-Item, Gate) und welche als **Anleitung** (SKILL) landen. Die
Trennlinie ist die aus der Verfassung: was mechanisch prüfbar ist, wird ein Gate; alles andere ist
Anleitung und darf nicht so tun, als wäre es erzwungen.

### 1a. Führung und Rangfolge — vom User nachgereicht (2026-07-27)

Zwei Anforderungen, die der Recherchekatalog NICHT abdeckt und die getrennt zu behandeln sind:

> „Es muss immer so designt sein, dass der Nutzer geführt wird und die wichtigsten Dinge zuerst
> ersichtlich sind."

Die Recherche liefert Anti-Slop (B1/B2/B5/B6) und Vollständigkeit (B4-Zustandsmatrix,
B7-Layoutkriterien) — also *dass nichts fehlt und nichts nach Standardausgabe aussieht*. Sie sagt
nichts darüber, **was zuerst kommt**. Das ist Komposition, nicht Konformität, und es ist die
Anforderung, die der User als Einziger beurteilen kann.

Vorschlag zur Umsetzung, im selben Muster wie der Rest:

- **SKILL, nicht Gate, für die Rangfolge selbst.** „Ist das Wichtigste zuerst sichtbar" ist Urteil.
  Ein Präsenz-Gate darauf wäre die Sorte Prüfung, deren Bestehen nichts aussagt.
- **GATE für das, was Rangfolge nachweisbar macht:** je View genau EIN primäres Ziel, als
  `data-primary-action` im eingefrorenen Vertrag ausgezeichnet. Fehlschlag beschreibbar: „View X
  deklariert null oder zwei primäre Aktionen." Damit ist „geführt" keine Meinung mehr, sondern
  eine Aussage, die der Entwurf trifft und der Build einhalten muss.
- **SKILL-Zeile mit Verfahren, nicht mit Adjektiv:** die Designerin benennt je View in einem Satz,
  was der Nutzer hier tun soll und woran er es zuerst sieht. Ein Entwurf, der diesen Satz nicht
  hergibt, hat keine Rangfolge — das ist der Selbsttest, analog zur Klischee-Kalibrierung.
- **In die heuristische Evaluation (B9) aufnehmen** — die Nielsen-Heuristiken decken Sichtbarkeit
  des Systemzustands und Wiedererkennung statt Erinnern ab, aber nicht „eine Sache pro Ansicht".

Offen bleibt bewusst: ob die Rangfolge in den WFR (Wireframe, vor der Gestaltung) gehört statt in
die DSN. Sachlich gehört sie dorthin — Rangfolge ist eine Struktur-, keine Stilentscheidung.

**Item:** → FR-0078 — ein Gate auf genau EIN primäres Ziel je View, plus die SKILL-Zeile mit
Verfahren statt Adjektiv. Gilt für diesen Abschnitt und für Abschnitt 1 darüber.
**Geliefert in TSK-0119, als PRÜFUNG im ausgelieferten Skript und nicht als Haken:** die Designer-
Rolle schreibt je View einen Satz („hier tut der Nutzer X, und er sieht es zuerst an Y"), zeichnet
den Container mit `data-view` und das eine Element mit `data-primary-action` aus, und
`kit_design_render.py` verweigert am gerenderten DOM jeden **deklarierten** View mit null oder
mehr als einem — mit dem Satz, der die Rangfolge einfordert. Was es ausdrücklich NICHT tut: einen
View beurteilen, den niemand deklariert hat (`H140`). Warum kein Haken: `DEC-0056` baut kein Gate
für eine Fehlklasse ohne gemessenen Fall, und der einzige gemessene Fall dieser Gegend ist
`BUG-0076` (ungesehener Entwurf), den `gate_design_sighted` schon trägt — der Preis dieser Wahl
steht als `H138`.

### 1b. Claude Design — nicht einbetten, aber anschlussfähig bleiben (2026-07-27)

`claude.ai/design` (Anthropic Labs, April 2026, Beta seit Juni) ist ein gehostetes Produkt: Repo und
Designdateien rein, Designsystem und Prototypen raus, iteriert über eine Leinwand mit kontextuellen
Reglern. **Nicht einbettbar** — die einzige Schnittstelle ist ein gehosteter MCP-Server mit
interaktivem Login, die Synchronisation ist bidirektional (zweite Quelle der Wahrheit neben dem
eingefrorenen Vertrag), und der Mehrwert liegt in Interaktivität, die ein Subagent nicht nutzt.

**Was wir stattdessen tun: das Bündel-FORMAT übernehmen, für null Aufwand.** Sein Übergabe-Bündel
ist strukturell unser Vertrag — `design.html` (eigenständig, CSS/JS inline), `screenshots/` (ein
Bild je Zustand), `design-notes.md` (Zielstack, Konventionen). Wenn die Designer-Rolle in
`staging/<task-id>/` genau dieses Tripel erzeugt, bleibt der Ablauf offline UND ein von Hand
exportiertes echtes Bündel lässt sich ohne Umbau einlegen.

Vor der Festschreibung als Vertragsschema: **einmal ein echtes Bündel exportieren und die
Dateinamen verifizieren.** Die Zusammensetzung stammt bislang aus Sekundärquellen.

Inhaltlich bleibt es beim Apache-2.0-Skill `anthropics/skills` → `frontend-design` (~12 Zeilen:
Klischee-Kalibrierung mit Hex-Werten, Selbsttest-Verfahren, UI-Text-Abschnitt). Das Produkt liefert
keinen lizenzfrei verwendbaren Text.

**Erledigt:** → FR-0045 — in der ersten Strom-Generation geliefert (DEC-0060, TSK-0100).

### 1c. Was als ANLEITUNG eingebaut wurde — und welche Gates dabei bewusst nicht entstanden (2026-08-03)

Die Trennlinie oben ist in dieser Runde **einseitig** aufgelöst worden: die Standards sind als
Verfahren in die betroffenen Spezialisten-SKILLs gewandert, **kein einziges neues Gate**. Der Grund
ist Erfahrung und keine Aufwandsschätzung — ein Gate, das im selben Paket entsteht wie der Text, den
es prüfen soll, wird gegen den Text gebaut statt gegen die Regel.

**Wo die Anleitung gelandet ist** (alle ausserhalb des Lead-Pakets, die Ratsche in
`tools/lead_package_sizes.json` blieb also unberührt): unter
`team-kits/dev-team/skills/` die Rollen `product-designer`, `frontend-developer`,
`backend-developer`, `software-architect` und `quality-engineer`, je ein Abschnitt
„Standards … — guidance, and NOTHING below is enforced"; dazu die zwei
Textrollen des Office-Kits (`product-editor`, `shop-curator`), die die Recherche selbst als
einschlägig für den Klartext-Grundsatz vermerkt hatte. Jede Zeile ist als **Selbsttest am eigenen
Ergebnis** formuliert, nicht als Standardname.

**Eine Ehrlichkeitsschuld ist dabei mitbezahlt worden** (X1 der Synthese, gemessen):
`quality-engineer/SKILL.md` behauptete „coverage ≥ threshold globally AND per source area".
`templates/repo/scripts/quality.py` baut in `check_python` genau **einen** `--cov=`-Sockel und
**ein** `--cov-fail-under=`; `gate_test_coverage` prüft je Bereich nur, ob es dort überhaupt eine
Testdatei gibt. Der Satz ist korrigiert und durch
`tools/test_role_contracts.py::test_the_qa_coverage_claim_matches_what_quality_py_measures` gepinnt.
Im selben Satz stand `component_coverage` — ein Name, den im ganzen Baum nichts erzeugt; er ist raus.

**Die mechanisch prüfbaren Hälften, eine Zeile je Kandidat, NICHT gebaut.** Die Nummern sind die der
Synthese (`docs/research/2026-07-27-SYNTHESE.md`, §1), wo Fehlerbild und Aufwand ausformuliert
stehen; hier steht nur, was die neue SKILL-Zeile offen lässt:

- **C1/C2/C3** — **GEBAUT in TSK-0119 (FR-0077), auf der gestagten DSN statt im `browser_smoke()`,
  und C1 ohne axe.** Was läuft: `kit_design_render.py` lädt jeden gestagten Entwurf ein zweites Mal
  und misst am gerenderten DOM Kontrast (WCAG 4.5:1/3:1), den Tastaturpfad (jedes fokussierbare
  Element per echtem Tab erreichbar; Fokus **in Pixeln** sichtbar; nichts, was die Maus klicken kann
  und die Tastatur nicht erreicht; kein positiver `tabindex`), die `prefers-reduced-motion`-Wirkung
  (dieselbe Seite in einem Kontext mit `reduced_motion: reduce`, es darf nichts mehr animieren) und
  die Präsenz einer `:focus-visible`-Regel. Rückgabe **3** statt 0, Datensatz wird trotzdem
  geschrieben. Die Bedingung des Abschnitts ist eingehalten und gemessen: der Bericht sagt „the
  automatically checkable share", nie „barrierefrei"
  (`tools/test_design_conformance.py::test_the_report_never_calls_a_draft_accessible`).
  **Drei Abweichungen, alle gemessen statt behauptet:** (a) **kein axe-core** — axe ist ein
  npm-Paket, und das Kit liefert gar keine npm-Datei aus, in die es gehören könnte (`templates/repo/`
  trägt `requirements-dev.txt`, `ruff.toml` und `scripts/`); die eine ausgelieferte Abhängigkeitsdatei
  lag ausserhalb der Dateihoheit dieses Stroms. Gebaut ist der Anteil, der ohne Abhängigkeit läuft.
  (b) **Subjekt ist der DSN-Entwurf, nicht der Build** — `kit_browser_checks.py` liefern dev-team
  UND research-team byte-gleich aus, und research-team war diesem Strom verboten; der Entwurf ist
  ausserdem der Vertrag, den der Build umsetzt, also die frühere Stelle. Die Build-Hälfte steht als
  `H139` unten. (c) **Unsichtbarer Fokus wird in PIXELN entschieden, nicht an byte-gleichen
  computed styles**, wie C2 oben vorschlägt: mit `a:focus { outline: none }` verschiebt Chromium
  `outline-offset` von 0px auf 1px, die computed styles sind also verschieden, und auf dem Schirm
  ist nichts — gemessen, und als eigener Fall in der Suite.
- **B2/B3** — **B2 gebaut in TSK-0119, B3 NICHT (Dateihoheit, siehe `H139`).** B2 läuft im selben
  Lauf: was ein Farbliteral ist, entscheidet der CSS-Parser des Browsers und keine Notationsliste —
  ein Wert ist ein Literal, wenn `CSS.supports('color', v)` gilt, er kein `var(` enthält, er kein
  CSS-weites Schlüsselwort ist (gefragt an einer Eigenschaft, die keine Farbe nimmt) und er unter
  zwei verschiedenen geerbten Farben gleich auflöst. Erlaubt ist er an **genau einer** Stelle: als
  Wert einer Custom Property. Das ist das Token-Blatt als Eigenschaft statt als Selektorliste, also
  auch für ein Theme-Block oder eine erfundene Schreibweise gültig. B3 (Farbliterale im
  Anwendungscode über `_frontend_sources()`) bräuchte `kit_checks.py` oder `kit_browser_checks.py`
  — beide ausserhalb dieses Stroms.
- **B2b** — Theme-Parität: die Tokennamensmengen unter `:root` und `[data-theme="dark"]` müssen
  gleich sein. Fängt den halbfertigen Dark Mode, den keine SKILL-Zeile fängt.
- **B4** — Präsenz der Zustandsvarianten je `data-view`. Die Designer-Zeile verlangt sie; dass sie da
  sind, ist zählbar, ob sie gut sind, nicht.
- **B5** — Platzhalter in sichtbaren Textknoten. **Warnung an den Erbauer:** die Recherche schlägt
  eine Wortliste vor, und eine Wortliste ist genau die Aufzählung, an der dieses Repo wiederholt
  bezahlt hat. Die SKILL-Zeile ist deshalb als Eigenschaft formuliert („ein sichtbarer String, der
  unverändert in ein ANDERES Produkt passt"). Wer das Gate baut, muss diese Eigenschaft
  mechanisieren oder die Liste als das benennen, was sie ist.
- **B6** — die Richtungen müssen sich auf mindestens einer deklarierten Achse unterscheiden.
- **D1** — `INV.check.ref` im State-Validator auflösen. **Der Multiplikator:** danach sind F4, F10
  und die INP-/SLO-Zeilen, die jetzt in drei SKILLs stehen, ohne neuen Gate-Code prüfbar. Solange er
  fehlt, sagen backend- und QA-SKILL ausdrücklich, dass ein fehlender Test bis zur QA unsichtbar
  bleibt.
- **D2** — assertionsfreie Tests per AST-Walk (nicht per Textsuche). Die QA-Zeile sagt heute „nichts
  in der Pipeline sucht danach".
- **D3** — Skip-/xfail-Buchhaltung aus `--junitxml`. Die QA-Zeile verlangt, die Zahl zu nennen; sie
  zu erzwingen wäre der Gate.
- **D4/D5** — der stille Frontend-Coverage-Fallback ohne `--coverage`, und Diff-Coverage gegen die
  Merge-Base statt eines höheren globalen Prozentsatzes. Nach der Korrektur oben ist D4 die einzige
  Stelle, an der die Pipeline heute noch grün meldet, was sie nicht gemessen hat.
- **A1/A2/A3/A4** — OpenAPI-Existenz und -Bindung an `SR.contract`, `application/problem+json` auf
  den deklarierten Fehlerantworten, Breaking-Change gegen die Merge-Base, `contract.kind` als
  geschlossenes Vokabular. Die Backend-Zeile prüft heute nur das Urteil („eine Route, die du
  aufrufen und im Dokument nicht finden kannst, ist Drift").
- **F9** — der Cross-Tenant-Negativtest je Operation mit Pfadparameter und `security`. Das ist die
  Fehlerklasse, die SAST strukturell nicht findet, und sie ist aus einem OpenAPI-Dokument
  vollständig aufzählbar — also erst nach A1.
- **F1/F2/F3/F6/F7** — `options_considered` ≥ 2 an richtungsgebenden Decisions, `arc_companion.scope`
  als C4-Vokabular plus beschriftete Kanten, `gate_threat_model` als Klon von
  `gate_packaging_decision`, `ARC.derives_from` nicht auf `SUPERSEDED`, SBOM bei verteiltem Artefakt.
  Von diesen ist F3 der einzige, dessen Fehlen die Architektur-SKILL heute ausdrücklich benennt.
- **F12/D8** — Migrationsform (Modelländerung ohne nummerierte Migration; `DROP`/`RENAME` ohne
  CR/DEC) und mindestens ein Test gegen die echte Engine bei deklariertem DB-Stack. D8 kostet Docker
  und muss dann **fehlschlagen** statt zu überspringen — sonst widerspricht er der QA-Regel, die er
  stützen soll.

**Was bewusst NICHT angefasst wurde, mit Grund:**

- **Die Lead-SKILLs und die Verfassungen.** Kein Standard aus der Recherche zwingt dorthin: die
  PM-Zeilen der Synthese (G3-Deutung, H1/H2, I3) hängen an Board, Meilensteinen und Mindmap — also an
  Abschnitt 2/3 dieser Liste, nicht an einem Standard. Damit blieb die Grössen-Ratsche unberührt und
  es war kein Nachziehen der Sektionspins nötig.
- **`research-team`.** Die Wunschliste nennt oben FAIR-Prinzipien, Datenversionierung und
  Reproduzierbarkeitspfade — **`docs/research/` deckt sie nicht ab.** Die zwölf Dateien dort sind
  sechs Rollenberichte (alle dev), vier Themenberichte und zwei Synthesen; keiner behandelt eine
  Research-Rolle. Etwas für `researcher`/`data-analyst`/`methodologist` zu schreiben hiesse hier
  erfinden, und die Anweisung war, es von dort zu nehmen. **Offen und benannt: eine
  Research-Rollenrecherche fehlt.**
- **Ein Präsenz-Gate auf „heuristische Evaluation durchgeführt".** Ausdrücklich nicht — sein Bestehen
  sagt nichts, und das verletzt die Hausregel in der zweiten Richtung.

**Zwei Baumbefunde derselben Runde, gemessen:**

- **Fünf der sechs Rollenberichte liegen unter dem falschen Rollennamen.** Gemessen an der ersten
  Zeile jeder Datei: `…-product-designer.md` analysiert `frontend-developer`,
  `…-frontend-developer.md` den `software-architect`, `…-software-architect.md` den
  `quality-engineer`, `…-quality-engineer.md` den `project-manager`, `…-project-manager.md` die
  `product-designer`. Nur `…-backend-developer.md` passt zu seinem Namen. Nicht umbenannt — die
  Dateien sind Belege, und ein `git mv` an Belegen ist eine Entscheidung des Users; wer sie liest,
  liest die Kopfzeile.
- **Spezialisten-SKILLs stehen unter KEINEM Sektionspin.** `test_shortening_net._pinned_files`
  bewacht Verfassung, Lead-Agentendatei, Lead-SKILL und `hooks/ENFORCEMENT.md` — die
  Spezialisten-SKILLs sind ausdrücklich draussen, und derselbe Modul-Docstring hält fest, dass ein
  gelöschter Satz aus `skills/backend-developer/SKILL.md` bei grüner Suite gemessen wurde. Der neue
  Anleitungstext ist damit **löschbar, ohne dass etwas rot wird**. `tools/test_role_contracts.py`
  pinnt nur den Ausgabekontrakt und die Coverage-Aussage, nicht die Standardabschnitte. Kandidat,
  bewusst hier statt gebaut: den Pin auf die Spezialisten-SKILLs ausdehnen — das ist eine
  Entscheidung über Kürzungsfreiheit, keine Textarbeit.

**Item:** → FR-0077 — die mechanisch prüfbaren Hälften C1/C2/C3 und B2/B3. **Geliefert in TSK-0119**
für C1 (ohne axe), C2, C3 und B2 auf der gestagten DSN; B3 und die Build-Hälfte stehen als `H139`.
Die Zeilen oben sagen je Hälfte, was läuft und was nicht.

## 2. Board- und Backlog-Ansichten

Der V2-Zustand ist erstmals die richtige Datengrundlage dafür: ein Vorgang = eine Datei, typisiert,
mit Statusautomat, und Abgeschlossenes verlässt den aktiven Kontext.

Gewünscht:

- **Kanban-Board** über die aktiven Vorgänge. Abgeschlossenes ausblenden ist bereits geschenkt —
  terminale Items liegen im Archiv, nicht in `*/active/`.
- **Karten zeigen nur den Titel**, aufklappbar für die Beschreibung.
- **Backlog-Ansicht** mit Gliederung, zwei Sichten:
  - *Produktebene* — PR/FR in Kundensprache,
  - *Systemebene* — SR/TSK, gegliedert nach Bereich.
- **Timeline** mit Fortschritt und Zielen.

Zwei Dinge fehlen dafür im Zustandsmodell, beide sind Entscheidungen:

1. **Die Gliederungsebene über dem Requirement** („Frontend" → „Buttons" → Requirement → Tasks).
   Jira nennt das Epic/Komponente, Azure DevOps Area Path. Empfehlung: ein **Feld** (`area`,
   mehrstufig als Pfad) an PR/SR/TSK, kein neuer Item-Typ — ein neuer Typ zöge einen
   Statusautomaten, Pflichtfelder und Freigabewege nach sich, die eine reine Gliederung nicht
   braucht.
2. **Termine für die Timeline.** V2 hat Meilensteine bewusst abgeschafft, weil `progress.yaml` sie
   doppelt führte. Eine Timeline braucht sie zurück — dann aber als eigener Vorgangstyp (MST) mit
   Datum und Zielbezug, nicht als Feld in einer Sammeldatei. Das ist die Entscheidung, die vor der
   Umsetzung fallen muss.

Technisch: die Ansichten gehören nach `generated/` (regenerierbar, nicht committet), gespeist aus
`generated/index.yaml`. Der Dashboard-Generator existiert bereits als Anknüpfungspunkt.

**Item:** → FR-0024 — deckt diesen Abschnitt und sagt es selbst; geliefert dagegen: FR-0030 und FR-0053, offen daneben FR-0017. Die Termine als eigener Vorgangstyp (MST) sind seither → FR-0079.

## 3. Der Plan als Bild, nicht nur als Text

Gewünscht: die Umsetzungsschritte zusätzlich als **draw.io-Diagramm** auf einer Flughöhe ohne
Fachjargon — man soll sehen, welche Schritte nötig sind und wo man steht. Dazu eine **Mindmap**, in
der sich schnell etwas ergänzen oder verschieben lässt.

Passt in die vorhandene Werkzeugkette: ARC- und WFR-Artefakte sind bereits `.drawio.svg`, das
Format ist also schon Teil des Zustandsmodells und wird bereits versioniert.

~~Offen: ob das Diagramm **generiert** wird oder **gepflegt**.~~ **Beantwortet durch
`docs/research/2026-07-27-plan-als-diagramm.md`: generiert.** Der übliche Einwand („generiert sieht
schlecht aus") heisst technisch „ein Programm kann keinen Graphen layouten" — das stimmt, die
mxGraph-Layoutalgorithmen leben im Editor, nicht in einer Python-Bibliothek. **Ein Umsetzungsplan ist
aber kein Graph, den man layouten muss.** Er ist ein Raster: Spalten sind Stufen, Zeilen sind
Vorgänge, Koordinaten sind eine Multiplikation. Damit fällt der einzige echte Nachteil weg. Ein
`.drawio.svg` ist ein gültiges SVG mit dem `<mxfile>`-XML im `content`-Attribut, derselbe
Layoutdurchgang kann also beide Hälften ausgeben — reines Python, kein Chromium, keine JVM. Mermaid
und PlantUML sind genau daran gescheitert: sie zögen eine fremde Laufzeit in einen Hook-Pfad, der
heute mit nichts als Python auskommt.

**Heutiger Stand, gemessen (2026-07-27):** die Werkzeugkette aus Spec II.6a existiert **als Zusage,
nicht als Datei** — `git ls-files | grep drawio` liefert null Treffer, es gibt kein Vorlagendiagramm
und kein `.vscode/extensions.json`-Template. Die einzige maschinelle Prüfung ist ein `ET.parse()` in
`kernel/staging.py`, während das Feld daneben `render_check: True` heisst. Das behauptet mehr, als es
prüft — dieselbe Klasse, die dieser Umbau an sechs anderen Stellen gefunden hat.

**Item:** → FR-0080 — Plan und Mindmap als generiertes `.drawio.svg`; das Format ist für WFR/ARC bereits in Gebrauch, das FR erweitert es.

### 3a. Nachtrag des Users (2026-08-03): der Zweck, und wo er der Ablage widerspricht

> „Weil so fallen schneller Unstimmigkeiten oder Missverständnisse auf als mit einer reinen
> Masterplan-MD-Datei."

Das ist ein **schärferer Zweck** als „sehen, wo man steht", und er entscheidet zwei Dinge, die bisher
offen waren:

**Erstens den Adressaten.** Ein Bild, das `SR-0004 → TSK-0011 (blocked by APR-0002)` zeigt, findet
keine Missverständnisse — es setzt voraus, dass der Leser die Typen kennt. Ein Bild, das „Anmeldung
funktioniert, bevor irgendetwas anderes gebaut wird" zeigt, findet sie. Die Flughöhe aus dem Absatz
oben ist damit keine Stilfrage, sondern die Funktionsbedingung: **wer den Jargon braucht, um das Bild
zu lesen, kann damit den Plan nicht mehr prüfen.**

**Zweitens die Ablage — und hier steht der Wunsch gegen die bisherige Empfehlung.** Der User will
Masterplan **und** Diagramm immer lokal im jeweiligen Repo. Die Recherche legt das Bild nach
`generated/` und committet es ausdrücklich **nicht** (Spec II.2: Ausgabe, kein Zustand — und genau
dadurch kann es nie veralten). Beides zusammen geht nur mit einer Entscheidung:

- **regeneriert bei jedem Zustandswechsel** — dann ist es immer aktuell, aber ein frischer Clone ist
  erst nach dem ersten Lauf bebildert;
- **mitcommittet mit Frischeprüfung** — dann ist es sofort da, kann aber veralten, und es braucht ein
  Gate, das die Abweichung meldet (dasselbe Muster wie die Delivery-Freshness aus II.12/R6).

**Empfehlung: mitcommittet mit Frischeprüfung**, weil der Zweck es verlangt. Ein Bild, das
Missverständnisse finden soll, muss jemand ansehen können, der das Repo gerade erst geöffnet und noch
nichts ausgeführt hat. Ein `generated/`-Artefakt ist für den Fortschrittsblick richtig und für den
Verständnisblick zu spät.

## 4. Effort-Stufen pro Rolle statt pro Modell (2026-07-31, User)

Vorschlag des Users: **alle Subagenten auf Opus**, und nur am Effort drehen. Modelltier ändert die
Fähigkeit, Effort die Gründlichkeit — ein Regler ist einfacher zu begründen als zwei.

Die Stufe sollte an **Unumkehrbarkeit** hängen, nicht an Dienstalter. Eine Entscheidung, die alles
Nachgelagerte einschränkt (Datenmodell, Architektur, der Plan), kostet bei einem Fehlgriff einen
Neubau; eine Implementierung innerhalb eines festen Scopes mit einem Test als Abnahmekriterium ist
prüfbar, und eine billigere Stufe plus Prüfung ist dort die bessere Ökonomie als eine teure Stufe
plus Hoffnung.

Daraus:

- **PM/Orchestrator, Architekt, Designer: `max`**, solange Plan, Architektur und Erstdesign stehen.
- **Danach Architekt und Orchestrator auf `xhigh`.** Wichtig: der Auslöser sollte **aus dem Zustand
  abgeleitet** sein, nicht aus der Zeit — der Harness kennt ihn bereits: sobald die scope-Freigabe
  geprägt und die Architektur-Items eingefroren bzw. die SRs akzeptiert sind, ist die Arbeit des
  Architekten inkrementell. Und eine `CR`, die die Architektur berührt, hebt ihn für diese CR
  zurück auf `max` — sonst ist die Stufe eine Einbahnstrasse und der späte Umbau bekommt die
  billige Stufe.
- **Frontend/Backend/DevOps: `low`–`medium`** ist vertretbar — aber nur unter der Bedingung im
  nächsten Punkt.
- **QA NICHT billig.** QA ist das, was die billigen Stufen erst tragfähig macht. Beleg aus dem
  V2-Umbau selbst: der Prüfer auf hoher Stufe fand in JEDER Runde, was der Umsetzer übersehen
  hatte, und zweimal fand er Tests, die gar nicht scheitern konnten. Wer den Prüfer verbilligt,
  verliert das Netz, mit dem er den Umsetzer verbilligt hat.

**Was das wirklich kostet:** Effort steht heute statisch in der Agentendefinition
(`.claude/agents/*.md`-Frontmatter). Eine zustandsabhängige Stufe heisst, dass der **Dispatcher sie
beim Spawn wählt** — das ist neue Mechanik im Kernel, nicht eine Konfigurationszeile. Das ist der
eigentliche Arbeitsposten dieses Punktes.

**Item:** → FR-0047; **Soll-Zustand entschieden in** → DEC-0034 (bewusst nicht gebaut), Besetzungsschicht → DEC-0059. Der gebaute Stand (`model_tiers.yaml`) und DEC-0034 weichen absichtlich voneinander ab.

## 5. Finanz-Vorlagen für das Office-Kit (2026-07-31, User)

Vorschlag: Vorlagen für **Bilanz, EÜR, Ledger**, weil Finanzen über Unternehmen hinweg nahezu
gleich sind — Produkte, Shop-Verwaltung und dergleichen dagegen spezifisch und Sache des
Office-Managers. Die Grenze ist richtig gezogen.

Präzisierung: der **Code** ist bereits generisch — `scripts/ledger_add.py`, `euer_report.py`,
`einvoice_extract.py` liegen im Kit. Neu erfunden wird jedes Mal das **Datenmodell**: der
Kontenrahmen (SKR03/SKR04), die Zuordnung Konto → EÜR-Zeile, die Gliederung der Bilanz. Die Vorlage
sollte also der Kontenrahmen plus die Abbildung sein, nicht ein weiteres Skript.

Zwei Bedingungen, sonst wird die Vorlage selbst zur Falschbehauptung:

- **Jahresversioniert.** Formulare und Zuordnungen ändern sich jährlich; eine Vorlage ohne Jahr ist
  ab dem nächsten Stichtag still falsch.
- **Rechtsraum benannt.** Eine Vorlage, die stillschweigend Deutschland annimmt, behauptet etwas,
  das sie nicht trägt — dieselbe Hausregel wie im Code.

**Nachtrag des Users (2026-07-31): gemeint ist vor allem die ANSICHT** — ein HTML-Dashboard, das
EÜR, Bilanz und Ledger darstellt. Das ist der fehlende Teil, nicht die Rechnung: `euer_report.py`
produziert die Zahlen bereits, es fehlt die Sicht darauf. Anknüpfungspunkt ist derselbe wie bei den
Board-Ansichten in Abschnitt 2 — `scripts/generate_dashboard.py` plus die HTML-Vorlage existieren,
gespeist würde die Finanzsicht aus den Ledger-CSVs statt aus `generated/index.yaml`.

Dabei gilt dieselbe Regel wie für die Board-Sichten, und im Finanzkontext ist sie strenger: die
Ansicht gehört nach `generated/`, **regenerierbar und nicht committet**. Eine committete Bilanz ist
eine zweite Wahrheit neben dem Ledger, und das Ledger ist der Beleg. Dazu eine Bedingung aus der
Erfahrung dieses Umbaus: die Ansicht muss **ihre Quelle und ihren Stichtag nennen**, sonst liest
jemand eine veraltete Zahl als aktuelle — dasselbe „abgeleitete Zahl ohne Ableitung", das im
Plandokument gefunden wurde, nur in einem Kontext, in dem Irrtümer Geld kosten.

Ergänzungsvorschlag zur generischen Seite: **Belegablage und Aufbewahrung** (GoBD) ist genauso
wenig unternehmensspezifisch wie die Finanzstruktur und hat mit `filing_plan.yaml` bereits einen
Ort im Kit.

**Item:** → FR-0032 für die ANSICHT (Finanz-Dashboard, geliefert in TSK-0109). Der Kontenrahmen SKR03/SKR04 mit der Konto→EÜR-Abbildung, jahresversioniert und mit benanntem Rechtsraum, ist → FR-0081; FR-0002 deckt Ablage und Aufbewahrung, nicht den Kontenrahmen.

## 6. Mehrere Spezialisten derselben Rolle parallel (2026-07-31, User)

**Heutiger Stand, gemessen:** verschiedene Rollen parallel ja, **dieselbe Rolle parallel nein.**
`kernel/dispatch.py` verweigert bei zwei wartenden Leases derselben Rolle mit `AmbiguousBinding`:
die Plattform gibt `SubagentStart` keinen Schlüssel, um die Kinder auseinanderzuhalten, und ein
Fehlgriff liesse einen Spezialisten unter fremdem `allowed_scope` laufen. Fail-closed statt Raten —
richtig, aber es ist eine Grenze, keine Absicht.

**Wünschenswert ist es klar:** drei unabhängige Frontend-Tasks parallel ist der Normalfall, und die
Lease-Mechanik (exklusiver Claim, TTL, Rückfall auf READY) trägt Parallelität bereits.

**Der Ansatz ist benennbar:** die Lease trägt eine **Nonce**, und die reist im
`HARNESS_DISPATCH`-Header im Prompt des Kindes. Bindet die Auflösung über die Nonce statt über den
Rollennamen, fällt die Grenze — vorausgesetzt, das Kind kann seine Nonce vor dem ersten
gescopeten Write nachweisen. Das ist die Messung, die vor der Umsetzung fällig ist (Spike S3 hat
`SubagentStart.agent_id == Kind-PreToolUse.agent_id` bereits belegt; offen ist der Weg von der
Nonce zur `agent_id`).

**Item:** → FR-0021 — nennt diesen Abschnitt selbst.

## 7. Ein dritter Evidence-Ausgang: `blocked` (2026-08-01, aus der Paritätsmatrix Zeile 99)

**Heutiger Stand, gemessen:** `EVIDENCE_RESULTS` (`team-kits/kernel/backlog_types.py`) kennt genau
`pass` und `fail`, und die Begründung daneben ist die richtige — ein Gate kann ein
„inconclusive" nicht auswerten, und ein Teillauf ist keine Merge-Evidenz. Der Fall, den das nicht
abdeckt, ist ein anderer: ein e2e-Lauf, der **umgebungsbedingt nicht stattgefunden** hat (kein
Browser, kein Gerät, kein Netz). Die Rolle muss ihn heute als `fail` buchen, und danach steht im
Store ein rotes Ergebnis, dem niemand mehr ansieht, ob wirklich etwas rot war oder ob nichts lief.
Genau das ist die Auskunft, die beim Lesen des Stores gebraucht wird.

**Wunsch:** `EVIDENCE_RESULTS += "blocked"`, und `gate_git` verweigert einen Merge, dessen neueste
`test`-Evidence `blocked` ist — dieselbe Behandlung wie `fail` an der Schranke, aber eine andere
Aussage im Store. Der Unterschied zu „inconclusive" ist, dass die Schranke nicht raten muss:
`blocked` schliesst, wie `fail` schliesst; nur der Grund ist ein anderer und bleibt lesbar.

**Aufwand: M.** Ein Wert im Frozenset, das Feldkontrakt-Schema, `gate_git`s Lesart der neuesten
Evidence je `kind`, die Rollen-SKILLs, die sagen, wann welcher Ausgang zu buchen ist, und die
Doktor-/Report-Sicht, die heute zweiwertig zählt.

**Der Satz, der dazugehört:** ob der zugrundeliegende Lauf wirklich übersprungen hat, bleibt
ausserhalb der Reichweite des Harness. Niemand misst nach, ob der Browser wirklich fehlte. Das Feld
macht aus einer Ehrlichkeitspflicht einen Zustand, keine Messung — es verbessert, was ein späterer
Leser erfährt, und es fügt der Frage „ist das wahr?" nichts hinzu. Wer es einbaut, muss diesen Satz
mit einbauen, sonst liest der nächste `blocked` als geprüfte Tatsache.

**Item:** → FR-0082 — `EVIDENCE_RESULTS` um `blocked` erweitert, `gate_git` schließt darauf wie auf `fail`, und der Ehrlichkeitssatz wird mitgebaut. Nachbar, nicht dasselbe: FR-0040.

## 8. Ein Projekt vollautonom von Anfang bis Ende (2026-08-03, User)

> „Wie bekommen wir es hin, dass ein neues Projekt vollautonom von Anfang bis Ende durchläuft — mit
> perfekter und getesteter UI, sauberem und sicherem Backend? Einen gereviewten Plan erstellen mit
> allen Wenn und Aber, alles so zerrupfen, dass am Ende ein Produktplan steht, und diesen vollautonom
> vom PM durchziehen lassen."

Das ist kein Einzelwunsch, sondern der Zweck, auf den die anderen sieben Punkte zulaufen. Deshalb
steht hier nicht „was man bauen müsste", sondern **woran heute gemessen fehlt**.

**Item:** → FR-0074; **entschieden in** → DEC-0058.

### Der Massstab existiert bereits, er hiess nur anders

Beim ersten Durchlauf des Lebenszyklus am Stück (2026-08-02, Testbed) musste ein Mensch **dreimal**
aus dem Harness ausbrechen, um bis zu einem Merge zu kommen: den Masterplan von Hand schreiben, eine
leere `requirements.txt` anlegen, `archive` raten. Ein autonomer Lauf hat diese Auswege nicht — er
folgt der Anweisung, die nicht hilft, und wiederholt sich.

**Damit ist Autonomiereife prüfbar statt gefühlt: die Zahl der Stellen, an denen zuletzt ein Mensch
improvisieren musste.** Sie ist endlich, sie wird bei jedem Durchlauf neu gemessen, und sie muss null
werden. Jede Sackgasse ist ein Autonomie-Stopper, unabhängig davon, wie klein sie aussieht.

### Was nach heutigem Stand fehlt

**Die Schreibsperre auf den Planungsdateien.** `masterplan.md`, `project_config.yaml` und
`filing_plan.yaml` haben keinen Schreiber (Wurzel 1 + Stufe II.11/4). Ein autonomer PM kann seinen
eigenen Plan nicht füllen. Härteste Blockade von allen.

**Anweisungen, die das Gate nicht aufheben.** Items sind nach dem Anlegen unveränderlich, also ist
jede Abhilfe der Form „korrigiere Feld X" strukturell unausführbar. Ein Mensch rät `archive`; ein
autonomer Lauf rät nicht.

**Die Freigaben — und das ist die Designentscheidung, nicht ein Defekt.** Das Harness prägt einen
Token NUR aus einer echten Antwort auf eine echte Frage. Das ist der Kern seiner Sicherheit und
zugleich genau das, was „vollautonom" ausschliesst. Die Frage lautet nicht „wie schalten wir das
ab", sondern **welche Freigabeklassen ein autonomer Richter erteilen darf und welche am Menschen
bleiben.** Scope und Delivery sind vermutlich verschieden zu behandeln; ein Push wahrscheinlich nie.
Ohne diese Entscheidung ist der Rest dieses Abschnitts akademisch.

**Das UI-Review mit Screenshots existiert nicht.** Die Design-Pipeline (Wireframe → Ambition →
Richtungen → Mockups → Fidelity) steht in der Verfassung ausdrücklich als **Prosa ohne Gate**. Kein
Mechanismus rendert, vergleicht oder urteilt. Der grösste echte Neubau: Headless-Render, Bild-Diff
gegen den eingefrorenen Mockup, und ein Richter über die Abweichung. II.12/R5 nennt einen
UI-Inventar-Snapshot — der fängt entfernte Elemente, nicht Aussehen.

**Das Backend-Testen hat einen Boden, keinen Beweis.** `quality.py` fährt Ruff, Mypy, Pytest, Bandit,
pip-audit, Dateibudget. Das schliesst Schlamperei aus, nicht Fehler. Für „sauber und sicher" fehlen
ein e2e-Lauf, der als solcher zählt (heute ist ein übersprungener Lauf nicht darstellbar — Punkt 7),
und eine Abdeckungsaussage über die *richtigen* Zeilen.

**Und die Planungsstufe selbst.** Das Kit kennt Masterplan → PR → SR → TSK. Was fehlt, ist die Stufe
davor: ein **gereviewter Plan**, der die kritischen Stellen benennt, bevor irgendetwas zerlegt wird.
Genau das, was für diesen V2-Umbau von Hand entstand — Paritätsmatrix, Löschlizenzen, benannte
Grenzen — nur als Produktplan. Punkt 3a gehört dazu: der Plan muss als Bild lesbar sein, sonst prüft
ihn niemand.

### Die Reihenfolge, die sich daraus ergibt

1. Sackgassen schliessen (Wurzel 1, Stufe II.11/4) — ohne das ist jeder weitere Punkt wirkungslos.
2. Die Freigabefrage entscheiden — sie bestimmt, was „autonom" überhaupt heissen darf.
3. Die Planungsstufe bauen, samt Bild (Punkt 3/3a).
4. UI-Review und e2e-Beweis (Punkt 1, Punkt 7).
5. Erst dann ein Durchlauf, dessen Ergebnis etwas über das Produkt aussagt statt über das Harness.

## 9. Der Masterplan braucht einen Zustand (2026-08-03, User)

**Das Modell des Users, in seinen Worten:** der Masterplan (MD **und** Diagramm, Punkt 3/3a) wird
zwischen ihm und dem Lead so lange durchgesprochen, bis alles Offene geklärt ist — „welche API wird
nötig sein", „wie soll das Design aussehen", „woher bekomme ich die Finanzberichte", „woher die
Kurse", „wie soll das Komitee aufgebaut sein". Erst dann die Freigabe, dann die Umsetzung, dann
autonom.

Seine Begründung ist die wichtigste Zeile dieses Abschnitts: **„Vieles fällt normalerweise erst
während der Umsetzung auf, deshalb muss man das penibel reviewen."**

**Heutiger Stand, gemessen:** der Masterplan trägt **keine Freigabe und keinen Zustand**. Die
scope-Freigabe hängt am `PR`, gehasht sind `problem`, `goal`, `acceptance_criteria`, `out_of_scope`,
`invariants`, `design_refs`. `product/masterplan.md` liegt daneben als lesbares Gesamtbild — ohne
Statusautomat, ohne Freigabe, und (Punkt 11/L1) ohne Schreiber. Er ist genau das Artefakt, das der
User als zentral beschreibt, und mechanisch ist er Prosa, die nichts bewacht.

**Das Harness behandelt späte Erkenntnis heute bestrafend statt vorbeugend:** wer nach der Freigabe
ein gehashtes Feld ändert, verliert sie, das Item fällt auf DRAFT zurück und braucht eine `CR`. Das
ist richtig und teuer. Was fehlt, ist die andere Hälfte.

**Der baubare Teil — eine Bedingung, kein Urteil:**

> Eine scope-Freigabe wird nicht angeboten, solange der Plan offene Fragen führt, die weder
> beantwortet noch ausdrücklich vertagt sind.

Der Masterplan hat die Sektion „Risiken & offene Fragen" bereits. Das Gate liest einen **Zustand**
(„steht dort noch etwas Unbeantwortetes?"), es urteilt nicht über Planqualität — dieselbe Trennlinie
wie überall im Kit. Es erzwingt genau die Runde, die der User beschreibt, **vor** der Freigabe statt
in der Umsetzung.

**Der Schnitt zwischen Mensch und Autonomie, der sich daraus ergibt:**

| Freigabe | Übergang | wer |
|---|---|---|
| `scope` | DRAFT → APPROVED | **Mensch** — die unumkehrbare Entscheidung, und der Ort des Reviews |
| `delivery` | APPROVED → IN_DELIVERY | **autonom** — durch den freigegebenen Scope begrenzt, jedes Gate prüft dagegen |
| `acceptance` | DELIVERED → ACCEPTED | **Mensch** — Urteil über das Ergebnis, blockiert aber nichts |
| `push` | (Token, an Remote+Branch+HEAD gebunden) | **Mensch** — Userentscheid 2026-08-03, ausnahmslos |

Ausdrücklich festgehalten, damit es nicht neu verhandelt wird: **ein Commit braucht keine Freigabe,
ein Push immer** (Userentscheid 2026-08-03).

**Teilweise erledigt:** die scope-Freigabe bei offenen Planfragen → DEC-0058 / FR-0074. **Offen bleibt die andere Hälfte:** der Masterplan hat nach der Installation keinen Schreiber — das ist L1 dieser Liste und wird dort geführt.

## 10. Die Freigabe programmatisch erteilen — und was das verschiebt (2026-08-03)

**Gemessen:** `AskUserQuestion` existiert im `-p`-Modus nicht. 30 Werkzeuge in der Init-Zeile, keines
davon; `--tools "Read,AskUserQuestion"` liefert `['Read']` — das Werkzeug wird still fallengelassen.
Auch `--input-format stream-json` ändert daran nichts. Damit fehlt der Kette headless ihr
NUTZERKANAL: keine echte Frage, keine echte Antwort, also kein Ja, das jemand gegeben hat.

**Korrektur 2026-08-30 (TSK-0097):** dieser Absatz schloss bis dahin mit „Da `gate_approval` **nur**
aus einer echten Antwort auf eine echte `AskUserQuestion` prägt, ist die Freigabekette headless
unerreichbar". Die Prämisse ist widerlegt — der Haken prägt aus **jeder** stdin-Nutzlast, die die
Form einer Antwort hat, und die Wand, die das in einem Kit aufhält, ist `gate_write_scope` und nicht
`gate_approval`. Gemessene Kette und Gegenmessung: **H80**. Headless unerreichbar ist also der
ehrliche Weg, nicht der Mechanismus.

**Zweite Korrektur 2026-09-11 (TSK-0135, Befund B1) — und damit ist BUG-0017 als GEMESSEN
ABSICHTLICH geschlossen, nicht als Fehler behoben.** Der Satz, den beide Absätze oben voraussetzen,
lautete: *der PM bleibt headless am ersten Freigabe-Gate stehen*. Gemessen wurde etwas anderes. Zwei
echte `claude -p`-Läufe gegen ein fertig aufgesetztes Kit-Projekt (Aufzeichnung, Rohstrom und
Laufdaten in `tools/provider_observations.json` → `headless_pm_stop_point`) enden **beide mit
`stop_reason: end_turn` und NULL `AskUserQuestion`-Blöcken**: der PM liest Masterplan, Wurzel-Item
und Konfiguration, erzeugt den Sitzungsbrief, fährt `validate` — und gibt die Entscheidung dann
**in Prosa** an den Nutzer zurück, womit der Zug und im `-p`-Modus die Sitzung endet. Er steht also
nicht AM Gate, er **kommt nie dorthin**. Für BUG-0017 heißt das: der Mint-Mechanismus ist headless
nicht kaputt, sondern unerreicht — es gibt nichts zu reparieren, und was stattdessen gilt, ist die
Messung. Wer sie prüft, prüft den Datensatz, nicht diesen Absatz:
`tools/test_report.py::test_the_headless_stop_point_is_measured_and_is_not_the_approval_gate`.

**Recherchiert (2026-08-03), drei Wege:**

- **PTY-Emulation** (ConPTY/winpty/`script`/`expect`) startet eine interaktive Sitzung, aber ein
  Programm müsste dann eine Terminal-Oberfläche per Bildschirmabgriff bedienen. Kein Vertrag,
  jederzeit brüchig. **Nicht gangbar.**
- **`--remote-control`** registriert sich bei der Anthropic-API und pollt nach Arbeit; braucht einen
  vollen claude.ai-Login (API-Keys ausdrücklich nicht unterstützt), und die Gegenseite ist
  claude.ai im Browser oder die Mobile-App — **ein Mensch auf einem anderen Gerät.** Verschiebt das
  Problem, löst es nicht.
- **Das Claude Agent SDK ist der dokumentierte Weg.** `AskUserQuestion` löst dort denselben
  `canUseTool`-Rückruf aus wie eine Werkzeugfreigabe; das Programm antwortet mit
  `{behavior: "allow", updatedInput: {questions, answers}}`. Kein TTY nötig. Dokumentierte Grenze:
  **in Subagenten, die über das Agent-Werkzeug gespawnt werden, ist `AskUserQuestion` nicht
  verfügbar** — nur in der Hauptsitzung.

**Was das für die Sicherheit heisst, und das ist der Kern:** heute gilt *ein Token existiert ⟹ ein
Mensch hat geantwortet*, weil `AskUserQuestion` nur einem Menschen etwas zeigen kann. Über das SDK
wird daraus *ein Token existiert ⟹ das einbettende Programm hat entschieden*. **Das SDK löst die
Vertrauensfrage nicht, es verlagert sie** — vom Provider in unseren Code.

Damit hat Punkt 8 zum ersten Mal einen konkreten Bauplatz (`canUseTool`) und die Sicherheitsfrage
eine scharfe Fassung: nicht „soll das Harness autonom laufen", sondern **wer darf der Richter sein,
und woran erkennt man hinterher, dass er es war.** Ein Token, den ein Programm geprägt hat, muss
sich von einem unterscheiden lassen, den ein Mensch geprägt hat — sonst ist die Provenienz, auf der
`doctor` seine `hook_trust`-Aussage aufbaut, nur noch eine Behauptung.

**Ungeklärt und eine Messung wert:** ob der `PermissionRequest`-Hook mit `updatedInput.answers` für
`AskUserQuestion` dasselbe kann, ohne die CLI zu verlassen. Das wäre der billigere Weg. Die Doku
zeigt das Feld generisch („any field from the tool's input schema"), nennt aber `AskUserQuestion`
nicht als Beispiel.

**Item:** → FR-0083 — Freigabe über das Agent SDK (`canUseTool`), und ein programmatisch geprägter Token muss von einem menschlich geprägten unterscheidbar bleiben. Die „headless unerreichbar"-Prämisse ist seit TSK-0097 widerlegt (`H80`).

## 11. Löcherliste — gemessen, benannt, nicht geschlossen (Stand 2026-08-03)

Jede Zeile ist eine **Messung**, kein Verdacht. Sie stehen hier, weil sie den Umbau nicht
blockieren, aber jede von ihnen kostet jemanden später Zeit — und weil eine Aufgabenliste mit der
Sitzung stirbt, in der sie entstand.

### L1 — Drei Planungsdateien haben keinen Schreiber (härteste Autonomie-Blockade)

`product/masterplan.md`, `project_config.yaml`, `filing_plan.yaml`. `gate_write_scope` verweigert
jeden Werkzeug-Write unter `project_memory/`, die Shell-Route ebenso, und der Kernel hat für diese
Dateien keinen Schreiber. Die Verweigerung sagt das seit `876d237` **ehrlich** („no route from
inside this session — report the gap"), statt auf `validate` zu verweisen, das im selben Zustand
0 Fehler meldet.

Nicht geschlossen, weil die Sperre **Verfassungsrecht in allen drei Kits** ist und durch einen
bestehenden Test gepinnt. Die Reparatur gehört nach Stufe II.11/4, wo der Einstieg ohnehin auf V2
umgestellt wird. Für office ist es existenziell: `filing_plan.yaml` wird mit `rules: []`
ausgeliefert, also ist die Kernfunktion des Kits ab Installation tot — im Kit dokumentiert, aber
lebendig.

### L2 — Items sind unveränderlich, also ist jede „korrigiere Feld X"-Abhilfe unausführbar

Es gibt kein Kommando, das ein Feld eines angelegten Items ändert. `archive` ist der einzige Ausweg
und stand bis `876d237` in keiner Meldung. Betroffen sind heute noch: `premise_rechecks` (die
Validator-Warnung nennt ein Feld, das an einem existierenden PR nicht mehr schreibbar ist), und
`acceptance_criteria` an einem bereits freigegebenen `PROC`.

### L3 — Ein direkt gestartetes Gate verseucht sein eigenes Bündel

`python .claude/hooks/gate_dispatch.py` ohne `-B` legt `__pycache__` an, **bevor** derselbe Prozess
den Bundle-Hash bildet — es verweigert seinen eigenen Spawn, schon im ersten Lauf (gemessen).
`_gate.py` trägt `sys.dont_write_bytecode`, aber ein direkt gestartetes Gate führt `_gate.py` nie
aus. Der saubere Fix ist eine Zeile in `GATE_PREAMBLE` und damit ~15 Hookdateien × 3 Kits plus die
Preamble-Pins. Die Klasse dahinter ist grösser: **jeder** Python-Prozess auf dem Host, der
`.claude/kernel` ohne `-B` importiert, entwaffnet die Delegation eines Projekts.

### L4 — Schreibverben innerhalb einer Programmsprache

`sed -n 'w datei'` schreibt aus dem Programmtext heraus und ist kein Shell-Operator; `gate_write_scope`
fängt Umleitungs*operatoren*, nicht die Schreibverben fremder Sprachen. Dasselbe gilt für `awk`,
`jq`, `perl -e`, `python -c`. **Bewusst nicht geschlossen:** eine Liste dieser Verben wäre genau die
Aufzählung im Gewand einer Regel, gegen die dieses Repo gebaut ist — sie stimmt bis zum sechsten
Werkzeug. Ein benanntes Loch ist ehrlicher.

### L5 — Der Workspace-Trust verwirft die `allow`-Hälfte, und das Fenster ist Reibung, kein Loch

**Korrigiert am 2026-08-03; die vorige Fassung dieses Eintrags war falsch.** Sie behauptete, der
**ganze** `permissions`-Block werde verworfen und ein frisches Projekt laufe ohne die Sperren —
und schrieb „gemessen" daneben. Gemessen ist das Gegenteil (2026-08-03, claude.exe 2.1.220,
headless, ein **nie getrautes** Scratch-Projekt mit einer kit-förmigen `settings.json`): die
Sitzung meldet die `Ignoring`-Zeile und verweigert im selben Lauf `Read` auf `server.key` („File is
in a directory that is denied by your permission settings.") und den Lead-Spawn („Agent type
'project-manager' has been denied by permission rule 'Agent(project-manager)' from
projectSettings.") — die Meldung nennt Regel und Quelle. Die Gegenprobe im selben Lauf: eine
gewöhnliche `notes.txt` daneben wird gelesen, die Sperre ist also die Regel und keine Pauschale.
Das Fenster macht eine Sitzung damit **restriktiver**, nicht durchlässiger.

Was bleibt, ist das messbare Restproblem: `Ignoring N permissions.allow entries … this workspace
has not been trusted` überspringt genau die `allow`-Hälfte — **5 Einträge** in dev und research,
**2** in office (`team-kits/*/settings/settings.json`). `deny` bleibt vollständig in Kraft. Die
Folge ist **Reibung**: der Lead muss `git`, `python` und `pytest` einzeln bestätigen lassen, bis
der Workspace getraut ist. Und die Neustart-Anweisung des Scaffolds (`scaffold_team.sh` /
`scaffold_team.ps1`, die Schlusszeilen) erwähnt den Trust-Dialog mit keinem Wort — das stimmt
weiterhin und ist der eigentliche Kandidat: ein Satz mehr in derselben Meldung.

**Ausdrücklich nicht der Ausweg: die Regeln auf User-Ebene nachziehen.** Das funktioniert gemessen,
löst aber ein Problem, das es nicht gibt — die `deny`-Hälfte gilt ja bereits —, und es bezahlt mit
einer Regel, die dann in **jedem** fremden Repo des Nutzers gilt und die der Installer bei jedem
Update wieder einmergt (`user/claude/settings.json`, unioniert von `install.sh`/`install.ps1`).

### L6 — Rollenmemory ist vorgeschrieben und gesperrt — geschlossen am 2026-08-17 (BUG-0047, TSK-0072)

Der Eintrag war zusätzlich in einem Punkt falsch: er nannte `submit-result` als Auslöser.
Gemessen im Scaffold gegen die projekteigenen Hooks (2026-08-17) war das eigene Memory an
**jedem** Punkt gesperrt — während `IN_PROGRESS` mit „outside TSK-0001's allowed_scope", danach
mit „this subagent is not bound to a task". Es gab also kein Fenster, das `submit-result`
geschlossen hätte, sondern von Anfang an keines.

Geschlossen als **Regel 6** in `gate_write_scope` (`_own_craft_memory`): der Aufrufer schreibt
`<Providerverzeichnis>/agent-memory/<seine eigene Rolle>/**` und sonst nichts ausserhalb seines
Task-Scopes — vor und nach der Rückgabe, während der allgemeine Task-Scope danach unverändert
geschlossen bleibt. Alle drei Bedingungen sind abgeleitet (Payload-`agent_type`,
`kernel.presets.AGENTS_DIR`, `guard_memory_budget.MEMORY_DIR`).
`tools/test_hooks.py::test_a_role_writes_its_own_craft_memory_and_only_its_own` hält sechs
Richtungen, darunter fünf Verweigerungen; ein aufgeweitetes Fenster (Rolle aus dem Pfad statt aus
dem Aufrufer) wurde in einem Klon rot gemessen.

**Offen bleibt der Shell-Weg, und zwar absichtlich:** `handle_shell` löst keine Rolle auf, also
könnte ein Fenster dort nur jedes Rollenmemory für jeden Aufrufer öffnen. Die Verweigerung nennt
seit dieser Runde die Tür, die es gibt (Write/Edit-Werkzeug für einen Subagenten), statt „Hooks
and settings are maintained by the scaffold" — der falsche Grund, den dieser Eintrag zu Recht
anmerkte.

**Und offen bleibt eine Nicht-Kongruenz, die beim ersten Anlauf ein echtes Loch war** (vom
Prüfer gemessen, in derselben Runde geschlossen — zweimal, denn unter dem ersten Fix lag noch
eine Namensschicht: Gate und Wächter urteilten über verschieden geschriebene Pfade, geschlossen
als EINE Ableitung `guard_memory_budget.guard_relative` mit zwei Lesern; beide Vertreter der
Schreibweisen-Klasse — ADS-Datenstrom und 8.3-Kurzname — sind gemessen zu): das Fenster
entscheidet über **Pfad und Rolle**, der Inhaltswächter über die **Form des Payloads** — zwei
Mengen, die nicht deckungsgleich sind. Geschlossen ist das dadurch, dass das Fenster den Wächter
fragt, statt ihn anzunehmen (`guard_memory_budget.judges_this_write`), also fail-closed in
dieselbe Richtung. Was damit **verweigert statt gedeckt** ist: jede Payload-Form, die der
Wächter nicht rekonstruieren kann — ein `Edit` mit leerem oder nicht auffindbarem `old_string`,
ein `NotebookEdit`, ein Codex-`apply_patch` — jede Datei im Memory-Baum, deren Budget keine
Inhaltsregel trägt, und jedes Memory-File, das unter einer nicht-geebneten Schreibweise
adressiert wird (gemessen: `MEMORY.md::$DATA` mit sauberem Inhalt → rc 2). Ein Rollenmemory als
Notebook oder über Codex zu pflegen ist damit **nicht möglich**; das ist Über-Verweigerung mit
Ansage, kein Loch, und die Schliessrichtung wäre, den Inhalt dieser Formen im Wächter zu
modellieren (`guard_memory_budget.py`, „Modelling notebook content is phase 3"). Bewusst NICHT
angefasst: ob `guard_memory_budget.main` selbst `realpath` auflösen soll — das wäre die
Ausweitung einer Inhaltsregel mit eigener Fehlalarm-Frage und steht als eigene Entscheidung an,
nicht als Nebenwirkung dieser Runde.

### L7 — Eine Lease aus einer abgestürzten Sitzung kostet die volle TTL

`reconcile_unstarted_dispatches` greift nur, wenn der Spawn **nie startete**. Ein gestartetes,
dann abgebrochenes Kind hält seine Lease 900 s; `sweep-leases` sagt ehrlich, wie lange
(`still leased: TSK-0001 (527 s left)`), aber es gibt kein Kommando, das sie zurückgibt. Gemessen:
924 s Stillstand. Kandidat: `sweep-leases --force <TSK>` mit Journalzeile, oder eine Bindung an die
Session-ID.

### L8 — Die Push-Freigabe invalidiert sich durch ihren eigenen Datensatz

Gemessen: Mint für HEAD `6c2d5d1e` → der Lead committet den Freigabe-Datensatz → HEAD ist
`34ae1673` → `no live user approval for pushing 34ae1673`. Kostet **jedes Mal** eine zusätzliche
menschliche Freigaberunde. Kandidaten: ein Satz in §8 („die Freigabe zuletzt holen"), oder
`project_memory/approvals/**` in `.gitignore`.

### L9 — Kleinere, je einzeilig

- **`capture` kann seinen Body nicht aus `staging/` lesen** — die dokumentierte Heredoc-Form
  kollidiert mit dem Gate; der Ausweg führt Harness-Eingaben ins OS-Temp-Verzeichnis.
- **Ein BOM in `agents/<lead>.md` hebt die `agent:`-Bindung lautlos auf** (`agent_type` wird `null`),
  und kein ausgelieferter Check sieht es. PowerShell 5.1 erzeugt das BOM beim Zurückschreiben.
- **`scaffold_team.sh` schreibt das Label mit** — `kit_version` in `kit_state.json` lautet
  `"version: 2026.08.03-1"`. Wird nirgends ausgewertet, ist aber ein falsch geparster Wert im
  Vertrauensdatensatz.
- **Ein Skill, den zwei Agenten nennen, kollabiert auf ein Paar** — nur einer der beiden wird auf den
  Abrufweg geprüft. Heute nennt jedes Skill genau ein Agent, der Fall ist eine Änderung entfernt.
- **`CR.target_pr` / `BUG.related_pr` prüfen Existenz, nicht Wurzelzugehörigkeit** — ein `BUG` darf
  ein `HYP` nennen, und `_root_of` gibt dieses `HYP` als Wurzel zurück. Zwei Codestellen halten
  „related_pr == root" als Absicht fest; der Kernel erzwingt es nicht, und `validate` schweigt.
- **`withdraw-approval` fehlt** — eine geöffnete Freigabefrage lässt sich nicht zurückziehen. Gebaut,
  gemessen und wieder entfernt, weil **jedes** neue Unterkommando Ergänzungen in sechs ausgelieferten
  Texten verlangt.
- **Ein Gate, das stdin selbst leert, nimmt dem nächsten der Kette die Nutzlast** — fail-closed
  (`{}` → Verweigerung), gehalten von einem AST-Test über jeden ausgelieferten Hook.
- **Unter der Grössen-Ratsche prüft nichts, ob verschobener Text laden musste** — der Rekord schützt
  Bytes, nicht Semantik. Eine ableitbare Regel dafür ist nicht in Sicht.
- **Ob eine stderr-Notiz bei exit 0 das Modell erreicht, hat niemand gemessen** (TSK-0074) — der
  Plattformvertrag garantiert Text vor dem Modell nur bei exit 2; `guard_question_context` SAGT das
  in seinem Kopf, gemessen ist es nirgends. Jede exit-0-Notiz der Kits (Spawn-Hinweis, R2-Warnung)
  ist damit ein Signal unbelegter Reichweite — die schwache Klasse, und sie steht in beiden
  Kommentaren als solche.
- **Der Spawn-Hinweis feuert nur auf ein JSON-`true` als Boolean** (TSK-0074, `guard_agent_spawn`:
  die Notiz-Bedingung liest `is True`, die Pflicht-Prüfung davor nur die Anwesenheit des Feldes) —
  `"true"` als String oder `1` als Zahl passieren die Pflichtprüfung und erzeugen lautlos keine
  Notiz. Fehlrichtung ist Schweigen, gemessen im echten Hook-Prozess; benannt im Kommentar und hier.
- **`cp -r <repo>/project_memory <ziel außerhalb>` wird verweigert, obwohl nur gelesen wird**
  (TSK-0076, gemessen rc 2): Gate 1 liest jeden `cp`-Operanden als mögliches Schreibziel, und
  `project_memory` in einer schreibfähigen Zeile ist für jeden Aufrufer gesperrt. Über-Verweigerung
  der bekannten Fail-closed-Bauart (H19-Familie), kein Loch; Ausweg gemessen: ein Python-Skript
  kopiert lesend (`clone_state.py`-Muster) oder `git show HEAD:<pfad>`.
- **`git hash-object <datei>` stuft Gate 3 als historienschreibend ein — ohne `-w` schreibt es
  aber nichts** (TSK-0076, gemessen; Präzisierung Prüfer: MIT `-w` schreibt es sehr wohl ein Blob,
  die Einstufung ist also nur für die flaglose Form Über-Verweigerung). Kein Loch; Ausweg:
  `sha256sum`/PowerShell-`Get-FileHash` über die Datei bzw. `git show` + Vergleich.
- **Eine reine Lesezeile mit `grep -qE "…=+ .*(passed|failed)"` wird von Gate 1 verweigert**
  (TSK-0076-Prüfrunde, gemessen rc 2): das `.*` im quotierten Muster wird als relativer Pfad
  gelesen und auf `..` über der Repo-Wurzel aufgelöst — H19-Familie (Vorfahren-Regel), kein Loch;
  Ausweg: Muster ohne `.*`-Präfix formulieren oder die Ausgabe erst in eine Datei leiten.
- **Kernel-angehängte Aktenplan-Regeln tragen nie die optionalen Felder** (TSK-0078:
  `required_metadata`, `collision_policy`, `examples` — `add-filing-rule` hängt die fünf
  Pflichtfelder an, und kein späterer Weg ergänzt die optionalen; `filing.py` begründet es
  ehrlich, die Folge steht hier: wer sie will, schreibt die Regel vor der Installation oder
  wartet auf ein Änderungs-Kommando, das eine eigene Runde wäre).
- **Die Naht Verdikt→Bewegung der Ablage-Kette ist Verfahrens-Prosa** (TSK-0078): nichts bindet
  die zweite Clerk-Beauftragung mechanisch an die Verdikt-Datei — der Manager könnte
  paraphrasieren. Die Texte weisen es als Verfahren aus; die Begrenzung ist `gate_filing`
  (jede Bewegung wird trotzdem gegen den Plan geprüft) plus der Auditor.
- **Zwei Antworten auf „welcher Modellwert ist portabel"** (TSK-0078-Prüfer):
  `gen_provider_artifacts.py` hält die Spezialisten-Frontmatter an eine hartkodierte Menge,
  während `tools/validate.py` dieselbe Frage seit FR-0051 aus `model_tiers.yaml` ableitet.
  Nicht neu eingeführt, durch die Ableitung sichtbar geworden; Kandidat: der Generator fragt
  dieselbe Ableitung.
- **Ein Bestandsrest der Office-Wand, an HEAD wie nach TSK-0077 identisch offen** (Prüfer,
  Runde 2-4, gemessen rc 0): `A=archive/…; rm "$A"` — der Operand wird von der Shell aus einer
  Variablen derselben Zeile umgeschrieben, die der Wand-Leser nicht auflöst (dieselbe Klasse wie
  H47 am Repo-Gate; als MITFAHRER neben einer Freigabe seit TSK-0077 rc 2, allein weiter rc 0).
  Schließrichtung: die Zeilen-Zuweisungskarte. Die zweite Hälfte, die hier stand — `mv ARCHIVE/…`,
  `_filing.under` case-sensitiv, während NTFS faltet — ist seit TSK-0087 GESCHLOSSEN
  (`os.path.normcase` beidseitig in `under`, Test verzweigt selbst über `normcase` und misst
  damit das Dateisystem): der Prüfer jener Runde hatte gemessen, dass die Schreibweise nicht nur
  den Austritt, sondern auch die EINTRITTS-Wand samt der neuen Zweitlesungs-Mechanik aushebelte
  (`ARCHIVE/`- und `Archive/`-Landung rc 0 durch alle sechs Hooks, Datei real im Archiv).
- **Die Eigenschaftsaussagen der `ENFORCEMENT.md`-Zeilen haben keinen Leser** (TSK-0075, Prüfer):
  ein Draht verlangt, dass jede Warn-Art *vorkommt*, aber nicht, was über sie *behauptet* wird —
  gemessen mit einer frei erfundenen Zeile (falsche Wörter, nicht existierende Konstante, falsche
  Schwelle, gegenteilige Verhaltensaussage): 12 einschlägige Tests grün. Der Verfassungs-Draht
  derselben Runde zeigt die Bauform des Fixes (Aussage gegen den laufenden Hook messen); eine
  eigene Runde, falls gewollt. Bis dahin gilt: `ENFORCEMENT.md`-Prosa ist Wegweiser, nicht Beweis.
- **`tar --remove-files` leert das Archiv, ohne ein Kopierer-Verb zu sein** (Rest von BUG-0002).
  `tar --remove-files -cf /tmp/a.tar archive/fin` archiviert die Quelle und **löscht sie danach** —
  eine Verschiebung aus dem Archiv, gemessen **rc 0** am `guard_fs_tripwire`-Prozess. `_filing` liest
  Kopie/Verschiebung an der Aufrufkonvention (Ziel als zweites bzw. letztes Token); `tar` hat keine,
  steht darum in keiner `DEST_IS_*`-Familie und erreicht `moved_out_of_the_archive` nie.
  `SOURCE_DELETING_FLAGS` greift erst, NACHDEM `_move` eine Familie erkannt hat — für tar gibt es
  keine. Nicht geschlossen: ein Fangen hiesse einen zweiten, nicht-kopierenden Löschpfad zu bauen
  (tar mit quell-löschendem Schalter als Löschung der genannten Operanden), was über den
  Bug-Auftrag hinausgeht. Begrenzung bis dahin: Löschen unter `archive/` per `rm`/`del` fängt die
  Delete-Regel bereits; nur der tar-interne Löschweg ist offen.
- **Sechs office-eigene Inhaltsdokumente haben gar keinen Schreibweg** (TSK-0081, gemessen als
  Ableitung über `layout.is_project_document` + `layout.partial_writers` gegen das ausgelieferte
  Template-Verzeichnis): von 10 Kit-Dokumenten tragen 2 einen Teil-Schreibweg
  (`filing_plan.yaml` über `add-filing-rule`, `project_config.yaml` über `set-preset`);
  `business_profile`, `compliance_register`, `content_guidelines`, `marketing_plan`,
  `master_data`, `product_catalog` haben keinen — sieben mit `product/masterplan.md` als
  kit-übergreifendem Fall. Sie werden im Onboarding gefüllt oder bleiben leer; die
  Bookkeeper-Texte sagen das seit TSK-0081 ehrlich. Ein echter Schreibweg nach dem
  `add-filing-rule`-Muster wäre je Dokument eine eigene Runde.
- **Ein Hook-Eintrag ohne `timeout` wird vom Provider bei ≈600 s getötet, und der Kill ist ein
  stiller Durchlass** (TSK-0082, beide Rollen unabhängig in echten Provider-Sitzungen gemessen,
  claude.exe 2.1.239: 310 s und 560 s überleben mit gehaltener Verweigerung, 900 s wird getötet
  und der verweigerte Aufruf läuft — Klammer 560/900, Sitzungsdauer datiert den Kill auf
  ~600 s; ein GESETZTES `timeout` tötet exakt an seiner Zahl, gemessen bei 5 s). Konsequenz
  gebaut statt gemerkt: die Kits registrieren kein `timeout` mehr (die BEOBACHTETE Laufzeit aller
  28 office-Einträge liegt ≤0,405 s; die größte EIGENE Kindgrenze eines Gates außer
  `gate_pipeline` ist 20 s — beides Messwerte, keine Schranken), außer wo ein Hook eine EIGENE,
  kleinere Verweigerungs-Grenze trägt — dann
  muss das Fenster echt darüber liegen (`gate_pipeline` 1800 über seiner 1500-s-Kindgrenze);
  ein Test hält die Eigenschaft, `tools/provider_observations.json` trägt die Messung.

### L10 — Was ohne einen Provider unprüfbar bleibt

- Ob ein **Subagent** sein SKILL geladen bekommt. Für den Sitzungs-Agenten ist gemessen, dass er es
  **nicht** bekommt; der Spawn-Weg ist zweimal an einem Kind gescheitert, das den Auftrag ablehnte,
  bevor es antwortete. In `tools/provider_observations.json` als offen geführt.
- Ob **Codex** einen `@`-Import in `AGENTS.md` expandiert.
- Ob `AskUserQuestion` im **interaktiven** Modus genau den Payload liefert, den `gate_approval`
  erwartet. Die Gates prägen korrekt, wenn der Payload kommt (viermal gemessen mit rekonstruiertem
  Payload) — die Form des echten Werkzeugaufrufs ist ungemessen.
- Ob der Provider einen **nutzer-globalen `SessionStart`-Hook** (`kit_bridge_notice.py`,
  TSK-0081) in eine Sitzung mit projekteigenen SessionStart-Hooks mischt und dessen
  `additionalContext` zustellt. Gemessen sind Hook-Prozess und Registrierung; kommt die Notiz
  nicht an, bleibt P4-1 für das betroffene Alt-Projekt unverändert (der menschliche Weg steht im
  README-Abschnitt „Update"). Messpunkt des Live-Testlaufs.

### L11 — Laufzeit: nicht der Zustand, sondern die Prozessanzahl

`gate_memory_complete` wächst **nicht** mit der Projektgrösse (323 ms bei 8 Items, 331 ms bei 32).
Was der Nutzer spürt, kommt woanders her: ein Bash-Werkzeugaufruf startet **acht** Python-Prozesse
für die Shell-Gates. In einem gemessenen Durchlauf waren das 149 Aufrufe × 8 = 1 192 Interpreterstarts
allein dafür; der Median stieg von 4,72 s auf 6,30 s. Der Hebel ist nicht der Zustands-Walk, sondern
die Startkosten — dieselbe Kettenform wie beim Spawn-Pfad wäre der naheliegende Kandidat.

### L12 — Eine kit-spezifische Datei kann den Inhalt eines fremden Kits bekommen, und nichts merkt es

Vorgeführt am 2026-08-03: ein Umsetzer hat `session_status.py` blind von dev über office und
research gespiegelt und dabei **119 bzw. 19 Zeilen kit-eigenen Inhalt gelöscht**. Aufgefallen ist es
an `git diff --stat`, **nicht an einem Test**.

Der Grund ist strukturell: `session_status.py` steht in `KIT_SPECIFIC_HOOKS`, also greift
`test_shared_kit_files_identical` per Konstruktion nicht — und das ist richtig, denn die Datei SOLL
sich unterscheiden. Was fehlt, ist die Gegenrichtung: **nichts behauptet, dass eine als
kit-spezifisch erklärte Datei ihren kit-spezifischen Inhalt behält.** Die Ausnahme von der
Spiegelregel ist heute eine Erlaubnis ohne Gegenstück.

Der Kandidat ist ableitbar statt getippt: eine Datei in `KIT_SPECIFIC_HOOKS` muss zwischen je zwei
Kits **verschieden** sein — sonst ist ihr Eintrag entweder falsch oder jemand hat sie gerade
plattgespiegelt. Das ist dieselbe Form wie die zweite Schleife in `_assert_mirrored`, die eine
Ausnahme verwirft, die niemand braucht — nur andersherum.

Nebenbefund derselben Runde: Pythons `write_text` dreht Zeilenenden auf CRLF, während
`.gitattributes` `*.py text eol=lf` sagt. Fünf Dateien waren betroffen und sind normalisiert;
**vorbestehend** trägt `guard_yaml_valid.py` in allen drei Kits CRLF, obwohl git sie unverändert
meldet.

### Die Einträge des V1-Imports (L13–L18, Stand 2026-08-05)

Sie kamen mit der Migrationsrunde dazu (`TSK-0016`) und tragen deshalb, was Abschnitt 12 von jedem
Eintrag verlangt: den **Mechanismus**, die **gemessene Kette**, ein **Urteil** und — solange der
Eintrag offen ist — **was stattdessen begrenzt**. Jeder von ihnen hat einen Stolperdraht in
`tools/test_migrate.py`, der den heutigen Stand misst und rot wird, sobald sich das Verhalten
bewegt; `test_every_hole_a_test_measures_is_carried_by_the_hole_list` hält Eintrag und Messung
zusammen. **Keiner der sechs ist in den drei Feldkopien erreichbar** — das ist je nachgemessen und
der Grund, warum sie Einträge sind und keine Blocker.

### L13 — Ein Typ, den der Feldvertrag kennt und die Zuordnungstabelle nicht, hat keinen Ausgang

**Mechanismus:** `migrate._is_backlog_type` ist die Vereinigung zweier Karten — `REQUIRED_FIELDS`
(dieser Kernel legt Items dieses Typs an) und `v1_types()` (die V1-Statustabelle kennt den Typ).
Ein Datensatz, dessen Typ nur in der ERSTEN steht, ist eine Harness-Lücke, und der Trockenlauf sagt
das korrekt. Was er nicht kann, ist einen Weg hindurch anbieten: der Lauf verweigert, solange der
Datensatz steht, und `validate` meldet das Dokument, das ihn hält — beide Abhilfen zeigen
aufeinander.

**Kette (gemessen 2026-08-05, dev-Scaffold außerhalb des Repos, ein Datensatz eines solchen Typs
mit `status`):** `migrate --dry-run` exit 1, `BLOCKED (1) … IS a V2 item type, but spec II.10's
mapping table has no row for it … Remedy: record it with … capture DEC and report it`; im selben
Zustand `validate` → `error … holds 1 V1 backlog record(s) … Remedy: run … migrate --dry-run`.
Welche Typen das heute sind, leitet der Stolperdraht aus den beiden Karten ab, statt sie
abzuschreiben — wächst die Tabelle eine Zeile, schrumpft die Menge mit.

**Urteil: Rest, keine Angriffskette** — aber ein Sackgassenzustand für ein Projekt, dessen V1-Store
einen solchen Datensatz trägt.

**Was stattdessen begrenzt:** der Lauf verweigert (kein stiller Durchlass) und benennt die Lücke
ausdrücklich als Harness- und nicht als Projektlücke. Der Ausweg existiert — den Datensatz vor dem
Lauf aus dem Zustandsverzeichnis nehmen —, steht aber in keiner der beiden Meldungen.

**Stolperdraht:** `test_migrate.test_a_type_the_field_contract_knows_and_the_table_does_not_has_no_way_out`

### L14 — Ein Unter-Mapping kollidiert mit seinem eigenen Elternteil

**Mechanismus:** `scan_document` zählt die Namen, die ein Mapping sich gibt, **pro Objekt**
(`self_named`, nach Objektidentität); `build_plan` zählt die Ansprüche auf eine Id **pro
Schlüssel** (`claimants`). Ein Mapping INNERHALB eines Datensatzes, das dessen Id wiederholt, ist
ein zweites Objekt mit je einem Namen: der Zweig „ein Mapping, zwei Ids" schweigt, und der
Kollisionszweig verweigert beide Einträge — über EINEN V1-Datensatz, mit einer Abhilfe, die von
zwei verschiedenen Datensätzen handelt.

**Kette (gemessen 2026-08-05):** ein `PROC-0001` mit einem `detail:`-Mapping, das `id: PROC-0001`
trägt → zwei Einträge, beide `blocked`, beide mit „appears 2 times in this run, in
procedures.yaml"; `plan_is_executable` False.

**Urteil: Rest, Über-Verweigerung.** Der Lauf schreibt nichts Falsches; er verweigert mit einer
Begründung, die den Leser auf die falsche Fährte setzt.

**Was stattdessen begrenzt:** die Verweigerung selbst ist die sichere Richtung, und der Ausweg
(die Id im Unter-Mapping im V1-File entfernen) ist ausführbar — er steht nur nicht in der Meldung.

**Stolperdraht:** `test_migrate.test_a_sub_mapping_of_a_record_collides_with_its_own_parent`

### L15 — Die Wanderkennung hängt an einem Attributnamen statt an der Eigenschaft, verweigern zu können

**Mechanismus:** `layout._can_refuse` fragt, ob ein Modul `<x>.block(...)` aufruft. Das ist eine
Schreibweise, keine Eigenschaft. Ein registriertes Hook, das den Werkzeugaufruf anders beendet,
gilt als nicht verweigerungsfähig — liest es den Pfad eines Kit-Dokuments, ist dieses Dokument
keine Wand, und ein vollständig aufgegangener Speicher wird nach `legacy/` **verschoben**. Das Gate
liest danach eine abwesende Datei, und was ein fail-closed Gate damit tut, ist nicht die Sache des
Imports.

**Kette (gemessen 2026-08-05):** ein registriertes `PreToolUse`-Hook, das über eine eigene Funktion
mit `sys.exit(2)` verweigert und `project_memory/process_definitions.yaml` zusammensetzt →
`gated_documents` leer → das Dokument steht in `absorbed_documents` und wird verschoben.
Gegenrichtung im selben Lauf: dieselbe Datei mit der erkannten Schreibweise → Wand. Wie breit die
blinde Stelle ist, im selben Lauf über die **registrierten** Hooks der Kits gezählt: dev 10 von 19,
office 9 von 18, research 9 von 17 verweigern in einer Schreibweise, die diese Erkennung nicht
sieht.

**Urteil: offen, heute ohne Kette in den Kits.** Kein ausgeliefertes Hook, das anders verweigert,
liest ein Kit-Dokument: die einzigen Leser von Kit-Dokumenten sind `gate_memory_complete`
(dev/research) bzw. `gate_filing` (office) — beide mit der erkannten Schreibweise — und
`session_status`, das nichts verweigert. Die nächste Hookdatei, die ein Dokument liest, entscheidet.

**Was stattdessen begrenzt:** allein diese Menge — zwei Dokumentleser pro Kit, gemessen, beide
sichtbar. Technisch begrenzt nichts; die Erkennung ist die einzige Instanz zwischen einem Gate und
seiner verschobenen Datei.

**Stolperdraht:** `test_migrate.test_a_hook_that_refuses_without_the_recognised_spelling_is_no_wall`

### L16 — Eine Wand, die V1-Datensätze hält, wird ein Validator-Fehler, den kein Lauf mehr auflöst

**Mechanismus:** eine Wand wird nie nach `legacy/` verschoben (richtig so — ihr Gate läse danach
eine abwesende Datei), und ein Import entfernt einen Datensatz nicht aus seinem V1-File. Eine Wand,
deren Datensätze alle importiert sind, hält sie damit weiter; `validate` meldet sie nach SR-0001 als
Fehler, und kein weiterer Lauf ändert daran etwas.

**Kette (gemessen 2026-08-05):** Wand über `process_definitions.yaml` registriert → Lauf exit 0, 16
Items → `validate`: `error … holds 1 V1 backlog record(s)` (bzw. je nach Fixture mehr) → zweiter
Trockenlauf: `NOTHING TO DO`, exit 0 → dieselbe Fehlermeldung, unverändert.

**Urteil: offen.** Der Fehler ist wahr — dieselbe Sache liegt zweimal im Projekt —, nur hat der Lauf
keinen Weg, ihn aufzulösen.

**Was stattdessen begrenzt:** die Meldung ist ein `error` und blockiert damit Merge und Push, statt
still zu bleiben; auflösbar ist sie heute nur außerhalb der Sitzung (die Datensätze im V1-File von
Hand entfernen, das Dokument bleibt als Wand liegen).

**Stolperdraht:** `test_migrate.test_a_wall_that_holds_v1_records_is_a_finding_no_run_can_clear`

### L17 — Der Abschlusskriterium-Scan liest ein zu großes Dokument nicht mehr (Rest des Fixes)

**Mechanismus:** dieser Eintrag ist der Preis der Obergrenze, die in derselben Runde eingezogen
wurde. `report._check_no_v1_records_outside_the_archive` läuft im blockierenden Merge-Gate mit;
ohne Grenze kostete er ~1,5 s je MB (gemessen: 1 MB 1,42 s · 5 MB 7,42 s · 15 MB 26,73 s · 55 MB
90,79 s), also mehr als die 60 s, nach denen ein `PreToolUse`-Hook getötet wird — und ein getötetes
Hook ist ein Durchlass. Mit der Grenze wird ein Dokument über der Marke **nicht gelesen**: ob es
V1-Datensätze hält, ist danach unbekannt.

**Kette (gemessen 2026-08-05):** ein Kit-Dokument über der Marke mit einem `PROC`-Datensatz darin →
der Parser bekommt es nicht mehr zu sehen, `validate` meldet es als Fehler mit der Wendung
`NOT SEARCHED for V1 backlog records` **in der Mitte** der Meldung (seit der Umrahmung vom
2026-08-07 führt die Ursache, und die Prüfung folgt: „It is N bytes … . It was therefore NOT
SEARCHED for V1 backlog records"); ein Dokument unter der Marke im selben Lauf wird weiterhin
gelesen und sein Datensatz weiterhin gemeldet.

**Korrektur 2026-08-07:** die früher hier notierte Kurve war unter „PyYAML with libyaml" gemessen;
dieser Pfad ruft `yaml.safe_load` und damit den **reinen Python-Loader** (`yaml.SafeLoader`),
obwohl `yaml.__with_libyaml__` True ist. Nachgemessen mit
`report._check_no_v1_records_outside_the_archive` direkt (bester von 3, ein büroartiges
`filing_log.yaml`): 1 MB 1,85 s · 2 MB 2,90 s · 4 MB 6,36 s · 8 MB 18,01 s; die erste, kalte
Lesung jeder Größe liegt Faktor 1,7–2,7 darüber (2,9–4,2 s je MB). Das Gesamtbudget von 8 MB
kostet damit **~18 s warm und ~31 s kalt** — ein Drittel bis die Hälfte der 60 s, die ein
`PreToolUse`-Hook für **alles** hat.

**Feldzahl (gemessen 2026-08-07, dieselbe Auswahl, die der Scan trifft):** `synaipse` hält 20
Kit-Dokumente mit zusammen 5 114 314 B = **63,9 % des Gesamtbudgets**, seine größte Datei
`design.yaml` 1 015 193 B = **50,8 % der Einzelgrenze**; `portfoliomanaigement` liegt bei 12,2 %
bzw. 6,3 %. Die Antwort auf „trifft ein echtes Projekt die Grenze?" lautet damit nicht *nein*,
sondern **noch nicht** — und die Abhilfe („nimm die Datei außerhalb der Sitzung heraus") ist genau
der Griff, den `gate_write_scope` innerhalb der Sitzung verbietet.

**Urteil: GESCHLOSSEN mit benanntem Rest.** Der unbegrenzte Leser ist weg; unbekannt bleibt
unbekannt.

**Was stattdessen begrenzt:** „nicht gelesen" wird als Fehler gemeldet und nicht übergangen — der
Merge bleibt also zu, statt still durchzulassen. Der Preis ist die Gegenrichtung: ein legitimes
großes Geschäftsdokument im Zustandsverzeichnis (ein gewachsenes `filing_log.yaml`) blockiert dann
Merge und Push, bis es außerhalb der Sitzung herausgenommen oder geteilt wird. Die Meldung sagt das.

**Stolperdrähte:** `test_migrate.test_a_document_too_large_to_search_is_reported_as_unsearched_and_not_read`
und `test_migrate.test_the_whole_scan_budget_names_the_documents_it_did_not_reach`

### L18 — Die Wurzelwarnung schweigt für ein Projekt, das schon vorher keines hielt

**Mechanismus:** `migrate.root_item_warnings` spricht, wenn ein Lauf das letzte aktive Wurzelitem
ins Archiv nimmt. Sie ist damit an die **Änderung** geknüpft, nicht an den Zustand, den der Lauf
hinterlässt. Ein Projekt, das vorher keines hielt, hört nichts — obwohl danach dasselbe gilt, was
DEC-0013 als gefährlich benannt hat: das Setup-Phasen-Prädikat antwortet nein, und die fünf Gates,
die es lesen, gelten nicht.

**Kette (gemessen 2026-08-05):** frisches Zustandsverzeichnis ohne Wurzelitem, ein übersetzbarer
`PROC` → `root_items_after` = `{PR: [0, 0], RQ: [0, 0]}` → `root_item_warnings` = `[]`; der
schreibende Lauf druckt dieselbe Stille.

**Urteil: Rest, keine Angriffskette** — die Gates sind in diesem Zustand ohnehin schon inaktiv, der
Lauf schaltet nichts ab. Was fehlt, ist die Ansage.

**Was stattdessen begrenzt:** `doctor` und der Sitzungsbrief melden den Zustand unabhängig vom Lauf;
DEC-0013 macht das frische Wurzelitem zur ersten Aufgabe der ersten Sitzung nach der Migration.

**Stolperdraht:** `test_migrate.test_the_root_warning_is_silent_for_a_project_that_held_no_root_item_before`

### L19 — Ein V1-Speicher außerhalb der Domäne des Suchlaufs wird benannt und blockiert nicht

**Mechanismus:** der SR-0001-Scan durchsucht die YAML-Dokumente des Zustandsverzeichnisses. Was
kein YAML-Dokument ist, im Vorschlagsbereich (`staging/`) oder unter einem gepunkteten Pfad liegt,
wird seit TSK-0020 von beiden Lesern **benannt** (`migrate.search_coverage`,
`report.record_scan_coverage`), aber nicht als Befund geführt — also verweigert kein Gate.

**Kette (gemessen 2026-08-07):** Zustand mit gültigem Wurzel-Item + `project_memory/old_procs.yaml.bak`
mit `PROC-0001` (`status: ACTIVE`) → `validate` druckt `NOT SEARCHED old_procs.yaml.bak: …`,
`gate_memory_complete` auf `git merge` **rc 0**. Dieselbe Datei als `old_procs.yaml`: rc 2.

**Urteil: OFFEN, nicht schließbar ohne einen neuen Fehlklang.** Ein Befund über diese Klasse wäre
in jedem Projekt dauerhaft und unauflösbar: das Forschungs-Kit liefert 27 nicht-YAML-Dateien unter
`project_memory/` aus (`README.md`, `product/masterplan.md`, `reports/assets/**`), Dev und Office je
zwei. Als `error` ein Merge, den kein Projekt je besteht; als `warning` ein Alarm über einen Zustand,
den niemand verlassen kann.

**Die Gegenrichtung ist teurer, und sie ist gemessen (2026-08-08):** der Vorschlagsbereich ist nicht
aus Bequemlichkeit ausgenommen. Ein für `capture` vorbereiteter Item-Body trägt eine Id und einen
`status`, ist also für denselben Erkenner ununterscheidbar von einem V1-Datensatz —
`migrate.scan_document` liest zwei gewöhnliche Vorschläge unter `staging/PR-0001/` als `TSK-0001`
und `TSK-0002`. Würde der Scan dort suchen, verweigerte das Merge-Gate jedem Projekt den Merge,
sobald zwei Vorschläge im Zustandsbaum liegen — für den Normalzustand des Arbeitens.

**Was stattdessen begrenzt:** die Datei ist nicht mehr stumm — `validate` druckt sie pro Datei mit
Grund, `doctor` trägt sie unter `record_scan_coverage`, der Trockenlauf der Migration nennt sie unter
`NOT SEARCHED`. Seit TSK-0023 nennt der Grund **jede** Bedingung, die die Datei draußen hält, samt
der zugehörigen Abhilfe (vorher führte die Abhilfe für eine Nicht-YAML-Datei unter `staging/` auf
eine Datei, die weiterhin unsearched ist). Und der eigentliche SR-0001-Fall (das zurückkopierte
Monolith) trägt seinen V1-Namen und liegt damit *in* der Domäne; unter dieses Loch fällt nur eine
Datei, die jemand zusätzlich umbenannt oder verschoben hat.

**Restfall des Vorlaufs:** eine Datei unter gepunktetem Pfad, die kein YAML-Dokument ist, gilt als
`machinery` — weder durchsucht noch genannt. Das hält `.kernel.lock`, `.audit/hook_events.jsonl` und
ein `.gitkeep` je Item-Verzeichnis aus beiden Berichten; ein dort versteckter V1-Datensatz steht in
keinem.

**Stolperdrähte:** `test_migrate.test_the_dry_run_and_the_validator_answer_the_same_about_every_file`
(letzter Block: rc 0, rot sobald der Merge dafür verweigert),
`test_migrate.test_every_spelling_of_the_proposal_area_gets_one_answer_from_both_readers` (die
Gegenrichtung) und `test_migrate.test_every_file_under_the_state_root_gets_exactly_one_search_verdict`
(der Restfall).

### L20 — Ein V1-Speicher in einem kernel-geschriebenen Bereich steht in keinem Bericht

**Mechanismus:** `migrate.search_coverage` urteilt `kernel` über den **Bereich**, nicht über den
Schreiber: alles unter einem Pfad, den ein Kernel-Bauer nennt, gilt als Schreibung des Kernels und
wird weder durchsucht noch als „nicht durchsucht" genannt. Das ist die zweite stumme Klasse neben
`machinery`, und die weitere von beiden.

**Kette (gemessen 2026-08-08):** Zustand mit gültigem Wurzel-Item, `processes: {PROC-0001: {status:
ACTIVE}}` je einmal in `generated/`, in `archive/PROC/2026/` und in `product/active/` abgelegt →
Deckung `kernel`, `record_scan_coverage` nennt keine der drei, kein V1-Befund. `gate_memory_complete`
auf `git merge`: **rc 0** für `generated/` und `archive/PROC/2026/`; für `product/active/` rc 2 —
aber aus einem anderen Grund, der Item-Validator liest die Datei als Item ohne Pflichtfelder.
Dieselben Bytes eine Ebene höher: rc 2 mit `holds 1 V1 backlog record(s)`.

**Urteil: OFFEN.** Der Ausweg wäre eine Aussage darüber, welche **Namen** ein Kernel-Bauer in einem
Bereich erzeugt (Item-Dateien, `index.yaml`, Freigabe-Ids …) — also eine Tabelle pro Bereich, und
damit genau die Aufzählung, gegen die dieses Repo gebaut ist. `legacy/` müsste ohnehin ausgenommen
bleiben: dort liegen absorbierte V1-Dokumente absichtlich.

**Was stattdessen begrenzt:** in diese Bereiche schreibt kein Werkzeug einer Sitzung —
`gate_write_scope` verweigert jeden Tool-Write unter `project_memory/`, und der Kernel legt dort nur
seine eigenen Dateien ab. Eine Datei kommt dorthin nur über eine Shell außerhalb der Sitzung oder
einen Checkout. Und der Bereich, den ein Item-Validator ohnehin abläuft (die aktiven
Item-Verzeichnisse), verweigert den Merge trotzdem — mit einer Meldung über etwas anderes.

**Stolperdraht:** `test_migrate.test_a_v1_store_inside_a_kernel_written_area_is_in_no_report`

### L21 — Die Prosa-Regel entscheidet Wort-Kovorkommen, nicht Paarung

**Mechanismus:**
`test_migrate.test_no_shipped_text_says_an_import_arrives_at_its_initial_status_full_stop`
fragt drei Wortlisten an einem Satz ab: ein Import-Wort, ein Anfangsstatus-Wort, kein Wort der
anderen Tür. Ob der Satz die Hälfte **behauptet** oder sie **verneint**, sieht keine der drei.

**Kette (gemessen 2026-08-07 an den ausgelieferten Regexen, je eine Probe):**
`Imports arrive at their INITIAL status, never at the mapped one.` — falsch über dieses Harness,
**geht durch**; `A record the table calls unfinished is imported at its initial status.` — wahr und
harmlos, **wird abgelehnt**; `Importierte Items kommen im Anfangsstatus an und tragen keine
Freigabe.` — dieselbe Behauptung auf Deutsch, **geht durch**; `Every imported PROC arrives in DRAFT
and carries no approval.` — dieselbe Behauptung mit **benanntem** Status, **geht durch**. Deckung
über das abgeleitete Korpus: 2704 Sätze in 70 Dokumenten, 56 mit Import-Wort, 2 mit
Anfangsstatus-Wort, **genau einer** wird angesehen.

**Urteil: NICHT SCHLIESSBAR mit dem Instrument.** Die Paarung zu entscheiden ist eine Lesart; ein
Prüfer, der einen richtigen Satz meldet, ist schlechter als keiner — die zweite Probe ist bereits
dieser Fall und ist der Preis der ersten.

**Was stattdessen begrenzt:** der Docstring behauptet die Paarung nicht mehr, sondern nennt alle
vier Proben; und der Test **fällt**, sobald die Zahl der angesehenen Sätze null erreicht — eine
Prüfung, die nichts ansieht, ist kein grünes Licht.

**Stolperdraht:** derselbe Test (die Vakuum-Zusicherung), rot gesehen, indem der eine angesehene
Satz in `README.md` umformuliert wurde.

### L22 — Der Plan-Digest deckt den Plan, nicht das Harness

**Mechanismus:** `migrate.plan_digest` ist über das Plan-Objekt genommen. Eine Kit-Änderung, die den
**Inhalt** des Plans bewegt, invalidiert einen vorgelegten Plan (gemessen: ein zusätzlicher Eintrag
in `backlog_types.OPTIONAL_FIELDS` bewegt den Digest bei byte-identischem `state_fingerprint`,
unveränderten Flaggen und unveränderter Registrierung). Eine Kit-Änderung **unterhalb** des Plans —
wie `execute` schreibt, was der Plan beschreibt — bewegt ihn nicht.

**Kette:** Trockenlauf lesen → Kit-Update, das nur die Schreibhälfte ändert → `--plan <digest>`
läuft durch, weil der Digest stimmt, und schreibt anders, als der gelesene Trockenlauf beschrieb.

**Urteil: OFFEN, nicht blockierend innerhalb einer Sitzung** — die Kette braucht eine
Neuinstallation zwischen den beiden Hälften.

**Was stattdessen begrenzt:** die Verweigerungsmeldung nennt Code und Tabellen jetzt als dritte Art
von Eingabe und schickt an `doctor`, das die `kit_version` berichtet; und die Gegenrichtung ist
gemessen (`test_migrate.test_moving_the_kernels_own_contract_table_alone_moves_the_digest`, zweite
Hälfte): eine Konstante ohne Verdikt bewegt den Digest nicht — der Digest ist also kein
Versionsstempel und darf nicht als einer gelesen werden.

**Stolperdraht:** `test_migrate.test_moving_the_kernels_own_contract_table_alone_moves_the_digest`

### L23 — Zitate außerhalb der II.10-Nachträge prüft nichts

**Mechanismus:**
`test_disposition.test_every_citation_in_the_migration_addenda_carries_the_wording_it_cites`
prüft nur die Nachträge, weil nur dort die Konvention „Zitat in Anführungszeichen, Paraphrase
kursiv" gilt.

**Kette (gezählt 2026-08-07 mit dem Leser derselben Datei):** 35 zitatförmige Spannen in der Spec,
7 in den Nachträgen (alle auflösbar), 28 außerhalb, davon **17 unauflösbar**. Die frühere
Begründung („zitieren die Welt außerhalb dieses Repos") hält für die Mehrzahl und **nicht** für
drei: `Prefer Mermaid over draw.io` (eigenes früheres Kit-Ruling), `je <=150 Zeilen` (eigene frühere
Zeilengrenze), `Derived 1:1 from … v1.11` (Kopfzeile des eigenen V1-Ablageplans) — Artefakte dieses
Repos, die keine Zeile hier mehr trägt.

**Urteil: OFFEN.** Ein Zitat zurückgezogenen Textes liest sich genau wie ein falsch abgeschriebenes;
das zu trennen braucht die Paarung Regel↔Abschnitt, also eine Lesart.

**Was stattdessen begrenzt:** die Konvention gilt in den Nachträgen, dort sind alle sieben Zitate
geprüft, und der Test fällt, wenn die Nachträge fast keine Zitate mehr tragen.

**Stolperdraht:**
`test_disposition.test_every_citation_in_the_migration_addenda_carries_the_wording_it_cites`

### L24 — Die Pfadregel gilt im Kernel-Paket und wird nur dort gelesen

**Mechanismus:** die Regel „ein Verzeichnisname, den ein Bauer besitzt, wird nur in diesem Bauer
zusammengesetzt" ist ein Stolperdraht über `team-kits/kernel/*.py`. Ausgelieferter Code **außerhalb**
des Pakets setzt dieselben Namen von Hand zusammen, weil dort kein `ProjectState` in der Hand liegt.

**Kette (gemessen 2026-08-08, AST-Leser über `team-kits/**/*.py` ohne das Kernel-Paket):** die Zahl
der Stellen steht **nur** im Pin `test_kernel._COMPOSITIONS_OUTSIDE_THE_PACKAGE` und wird hier
absichtlich nicht wiederholt — bis 2026-08-08 stand sie an beiden Orten, und die Prosakopie war die,
die niemand nachzieht. Die Stellen selbst: `hooks/_kernel.py` (`generated`, je Kit dreimal gespiegelt),
`templates/repo/scripts/generate_dashboard.py` (`generated`; seit TSK-0115 nicht mehr auch
`archive` — das Dashboard zählt das Archiv nicht mehr, DEC-0065 (1)),
`templates/repo/scripts/retro.py` (`generated`, dev und research), seit TSK-0099
`templates/repo/scripts/kit_design_render.py` (`staging`) und seit TSK-0132
`office-team/templates/repo/scripts/invoice_intake.py` (`staging`: die Andockstelle legt den
Ablage-Vorschlag dorthin, wo der Clerk seinen ablegt, und laeuft wie die anderen Vorlagen-Skripte
stdlib-only im Projekt). Jede davon ist eine zweite
Schreibweise der Antwort eines Bauers: zieht `state.generated_path` um, liest der Bridge-Code
weiter am alten Ort und meldet ein Projekt fälschlich als greenfield; zieht `staging/` um, rendert
das Design-Skript ins Leere und `gate_design_sighted` verweigert jede Vorlage, weil es den
Datensatz am alten Ort sucht.

**Urteil: OFFEN, nicht blockierend** — die Kette braucht eine Umbenennung im Kernel, und der
Bridge-Pfad ist genau der, der ohne Kernel funktionieren muss (`_kernel.state_is_empty` antwortet
auch dann, wenn der Kernel nicht importierbar ist; ihn an einen Bauer zu hängen, verlegt eine
Bootstrap-Antwort auf den Kernel). Für die drei Vorlagen-Skripte gilt dasselbe eine Stufe weiter
draußen: sie laufen **im Projekt** und stdlib-only, wie ihre eigenen Köpfe sagen — im Kit-Repo gibt
es dort keinen `ProjectState` zu fragen, und einen Kernel-Import hineinzulegen würde genau den
kernelfreien Pfad aufgeben, den dieser Eintrag beschreibt. Deshalb ist der Zuwachs eine Zahl plus
eine Zeile hier und keine Code-Änderung.

**Was stattdessen begrenzt:** die Zahl ist gepinnt, und zwar in **beiden** Richtungen — eine neue
Stelle wird rot, und die letzte verschwundene Stelle wird ebenfalls rot, damit der Eintrag nicht
als toter Text stehen bleibt. Der Docstring der Regel behauptet ihre Reichweite nicht mehr für
allen Code.

**Stolperdraht:** `test_kernel.test_the_path_rule_stops_at_the_kernel_package_and_the_rest_is_counted`

### L25 — Ein Item-Body, der sich selbst nennt, ist von einem V1-Datensatz nicht unterscheidbar

**Mechanismus:** ein V2-Item trägt `id: SR-0001` und einen `status` — genau die Form, an der
`migrate.scan_document` einen V1-Datensatz erkennt. Die beiden sind für den Erkenner dasselbe. Was
die eigenen Items eines Projekts aus dem SR-0001-Scan hält, ist allein ihr **Ort**: kernel-eigene
Bereiche werden pauschal übersprungen (L20), der Vorschlagsbereich ebenfalls (L19). Ein Body, der
woanders landet — eine Kopie, ein von Hand gesichertes Item, ein aus `staging/` hochgezogener
Vorschlag —, wird als V1-Datensatz gelesen.

**Kette (gemessen 2026-08-08):** Zustand mit gültigem Wurzel-Item, Merge rc 0 → zwei Dateien
`project_memory/notes/SR-0001.yaml` und `SR-0002.yaml` mit je `id`, `status: PROPOSED` →
`validate` meldet **zwei** `holds 1 V1 backlog record(s)`, `gate_memory_complete` auf `git merge`
**rc 2**, und innerhalb der Sitzung räumt das niemand weg: `gate_write_scope` verweigert jeden
Tool-Write unter `project_memory/`. Dieselben zwei Bodies unter `staging/PR-0001/`: rc 0.

**Urteil: OFFEN, nicht schließbar mit diesem Erkenner.** „Ist dieses Dokument ein V2-Item oder ein
V1-Datensatz?" ist an der Form nicht entscheidbar; die einzige verfügbare Antwort ist der Ort, und
den nennt die Meldung bereits.

**Was stattdessen begrenzt:** kein Werkzeug einer Sitzung schreibt dorthin, der Kernel legt Items
nur in seine eigenen Bereiche, und der Vorschlagsbereich — der einzige Ort im Zustandsbaum, an dem
eine Rolle solche Bodies wirklich erzeugt — ist genau deshalb aus dem Scan heraus. Die Verweigerung
nennt die Datei, und die Abhilfe („nimm sie außerhalb der Sitzung heraus") ist ausführbar.

**Stolperdraht:** `test_migrate.test_two_item_bodies_outside_the_kernels_own_areas_refuse_every_merge`

### L26 — Der Kopplungstest schließt das Paar nur einseitig, und die Referenz ist eine Schreibweise

**Mechanismus:** `test_migrate.test_every_hole_a_test_measures_is_carried_by_the_hole_list` läuft
über die Menge der Einträge, die ein **Test nennt** (`named`), nie über die Einträge der Liste
(`entries`). Ein Eintrag, den kein Test nennt, wird deshalb von nichts geprüft — weder auf Urteil
noch auf Begrenzung noch darauf, dass sein zitierter Stolperdraht existiert. Zweite Aufzählung im
selben Test: `_HOLE_REFERENCE` ist **eine** Schreibweise (`` `L19` in `docs/POST_V2_WISHLIST.md` ``);
eine Nennung als „getragen von `L19`" ist kein Treffer.

**Kette (gemessen 2026-08-08 im Klon außerhalb des Repos, je eine Probe):** fehlender Eintrag zu
einer Test-Nennung ⇒ **rot**; Zitat auf einen umbenannten Test ⇒ **rot**; Eintrag ohne jede
Test-Nennung (verwaist), Urteil entfernt ⇒ **grün**. Ein verwaister Eintrag ist genau die Hälfte,
für die der Docstring bis heute „BOTH DIRECTIONS" behauptete.

**Urteil: OFFEN, nicht blockierend innerhalb einer Sitzung** — die Wirkung ist ein Eintrag, der als
toter Text stehen bleibt, kein Durchlass an einem Gate. Die Richtung „Test nennt einen Eintrag, den
es nicht gibt" ist die, an der ein Paket auseinanderfällt, und die ist zu.

**Was stattdessen begrenzt:** der Docstring behauptet die zweite Richtung nicht mehr, sondern nennt
sie als Lücke mit dieser Nummer; und die Einträge dieses Pakets sind alle von einem Test genannt,
liegen also in der geprüften Hälfte.

**Stolperdraht:** `test_migrate.test_every_hole_a_test_measures_is_carried_by_the_hole_list`
(die geprüfte Richtung)

### L27 — Der DEC-0021-Stolperdraht definiert „Leser" als zwei Operationen

**Mechanismus:** der Test parst allen ausgelieferten Python-Code und sammelt jede Stelle, die
`IMPORT_MARK` aus einem Mapping **holt** — als Subscript oder als `.get`. Das ist eine Aufzählung
zweier Operationen und keine Eigenschaft; die Marke ist eine Präsenzmarke, und die liest man am
natürlichsten mit `in`.

**Kette (gemessen 2026-08-08, je ein echter Leser in `kernel/report.py` eingesetzt und der Test
gefahren):** `IMPORT_MARK in item` ⇒ **grün**; `item.pop(IMPORT_MARK, None)` ⇒ **grün**; ein
Schlüsselvergleich `if name == IMPORT_MARK` in einer Feldschleife ⇒ **grün**;
`getattr(item, IMPORT_MARK, None)` ⇒ **grün**; nur das Subscript ⇒ rot. DEC-0021 entschied gegen
jeden Leser; vier von fünf Formen kämen unbemerkt hinein.

**Urteil: OFFEN, nicht blockierend** — ein Leser dieser Marke ist kein Durchlass, sondern eine
Entscheidung, die jemand ein zweites Mal treffen müsste. Die Eigenschaft sauber zu fassen („der Name
erscheint in einer Position, die nicht die Store-Seite einer Zuweisung ist") ist machbar und wurde
hier bewusst nicht gebaut: der Test liegt im Prüfwerk, nicht im Produkt.

**Was stattdessen begrenzt:** die **Schreib**seite ist vollständig gepinnt — der Test verlangt
exakt drei Schreibstellen, also wird eine vierte Stelle, die die Marke setzt, sofort rot; und der
Docstring behauptet nicht mehr, jeder morgen hinzugefügte Leser werde rot.

**Stolperdraht:** `test_migrate.test_the_import_mark_says_where_an_item_came_from_and_claims_no_lever`

### L28 — Die `UNLISTABLE`-Zeile entsteht für jeden Walk-Fehler, auch wo nie gesucht würde

**Mechanismus:** `migrate.search_coverage` hängt seinen `onerror`-Sammler an den **ganzen** Walk.
Jeder Fehler wird eine `UNLISTABLE`-Zeile, und beide Leser verweigern darauf — unabhängig davon, ob
unter dem Verzeichnis überhaupt gesucht worden wäre. Für `staging/`, für gepunktete Pfade und für
kernel-eigene Bereiche ist die Antwort auf ein lesbares Verzeichnis „wird nicht durchsucht"; die
Antwort auf ein unlesbares ist „der ganze Lauf wird verweigert".

**Kette (gemessen 2026-08-08, `icacls /deny <user>:(OI)(CI)(RD,RA)` auf je ein Verzeichnis eines
sauberen Zustands mit Wurzel-Item, `gate_memory_complete` als Prozess auf `git merge`):**
`.audit/` lesbar ⇒ **rc 0**, gesperrt ⇒ **rc 2** und die Meldung nennt das Verzeichnis; `staging/`
lesbar ⇒ **rc 0**, gesperrt ⇒ **rc 2**, ebenso benannt. Beide Verzeichnisse werden im lesbaren
Zustand von keinem Suchlauf angesehen. Die Abhilfe der Meldung verlangt eine Shell außerhalb der
Sitzung, weil `gate_write_scope` jeden Tool-Write unter `project_memory/` verweigert.

**Urteil: OFFEN als Über-Verweigerung, kein Loch.** Fail-closed ist hier die richtige Richtung: ein
Verzeichnis, das der Walk nicht öffnen kann, hat keinen Pfad, über den sich sein Inhalt einordnen
ließe — der Name im Fehler ist alles, was existiert, und daraus „hier wäre ohnehin nicht gesucht
worden" abzuleiten hieße, dem Fehlerpfad zu vertrauen, wo gerade nichts gelesen werden konnte.

**Was stattdessen begrenzt:** die Verweigerung nennt das Verzeichnis und eine ausführbare Abhilfe,
und sie ist nicht dauerhaft — Leserechte zurückgeben löst sie auf. Die Gegenrichtung ist gemessen:
dasselbe Verzeichnis wieder lesbar ⇒ kein Befund.

**Stolperdraht:** `test_migrate.test_a_directory_the_walk_cannot_open_is_named_and_refuses_the_run`

### L29 — Die Faltung des Vorschlagsbereichs ist `str.lower`, die des Dateisystems eine andere

**Mechanismus:** `layout.is_in_proposal_area` vergleicht das erste Pfadsegment nach `str.lower()`.
Ein Windows-Dateisystem faltet mehr als Groß-/Kleinschreibung.

**Kette (gemessen 2026-08-08 auf diesem Host):** `staging/x.yaml`, `Staging/x.yaml` und
`STAGING/x.yaml` — Dateisystem öffnet, Prädikat sagt ja. `staging./x.yaml` — Dateisystem öffnet
**dieselbe** Datei, Prädikat sagt **nein**; `staging../x.yaml` öffnet nichts. Ein V1-Speicher, den
jemand unter dieser Schreibweise anspricht, wäre also `searched` statt `unsearched`.

**Urteil: OFFEN, heute nicht erreichbar.** Jeder Aufrufer im Kernel füttert das Prädikat mit einem
Namen, den `os.walk` erzeugt hat, und ein Walk liefert den Namen, den das Verzeichnis wirklich
trägt — die abweichende Schreibweise entsteht nur, wenn ein Aufrufer einen von Hand getippten Pfad
hereinreicht. Ein Rest des **Prädikats**, kein Loch im Harness.

**Was stattdessen begrenzt:** die Richtung des Fehlers ist die harmlose beider Seiten — eine Datei
würde zusätzlich durchsucht und damit **gemeldet**, nicht verschwiegen; und der Docstring des
Prädikats nennt jetzt beide Reste statt nur den der Gegenrichtung.

**Stolperdraht:**
`test_migrate.test_every_spelling_of_the_proposal_area_gets_one_answer_from_both_readers`
(die gemessene Hälfte: die Groß-/Kleinschreibung)

### L30 — Zwischen der Frage nach dem Landeplatz und dem `os.replace` bleibt eine Spanne

**Was hier bis 2026-08-09 stand, ist weg statt begrenzt.** Der Eintrag beschrieb die gedruckte
Abhilfe des Trockenlaufs: sie nannte einen Landeplatz, der im Augenblick des Lesens frei war, und
der Leser handelte später in einer Shell außerhalb der Sitzung. **DEC-0024** hat diese Klasse
konstruktiv abgeschafft — eine Abhilfe nennt heute nur noch eine **Kopie** in die Ablage unter
`staging/`, die dieses Kommando selbst besitzt und in der der Name aus dem Quellpfad abgeleitet ist
(`migrate.deposit_of`). Sie schlägt keine Bewegung mehr vor, also gibt es dort keinen Platz mehr,
den jemand später besetzen könnte. Was übrig bleibt und diesen Eintrag jetzt trägt, ist die
**eigene** Bewegung des Kommandos.

**Mechanismus:** `migrate._retire_absorbed_documents` fragt `_is_occupied(landing)`, ruft dann
`os.makedirs` und danach `os.replace`. `os.replace` hat auf keiner der beiden Plattformen, auf denen
dieses Harness läuft, eine no-clobber-Variante: es ersetzt, atomar und wortlos. Zwischen Frage und
Ersetzung liegen also zwei Aufrufe, und eine Datei, die in dieser Spanne entsteht, wird von einem
Lauf weggenommen, der gefragt und „frei" gehört hat. Der frühere Satz an dieser Stelle — die eigene
Bewegung frage „dort, wo **keine Spanne** bleibt" — war damit eine Zusicherung, die der Code nicht
baut.

**Kette (gemessen 2026-08-09):** Zustand mit einem vollständig absorbierten `a.yaml`, Plan gebaut,
`occupied_landings == []`, `plan_is_executable` True. Die Spanne wird deterministisch besetzt, indem
der Aufruf besetzt wird, der wirklich dazwischen liegt (`os.makedirs` legt zusätzlich
`legacy/a.yaml` an). Ergebnis: der Lauf endet mit rc 0, `moved` nennt `a.yaml`, und der Inhalt von
`legacy/a.yaml` ist der des Dokuments — die fremde Datei ist ohne Meldung fort.

**Urteil: OFFEN, mit den heutigen Primitiven nicht ohne Umbau schließbar.** Ein no-clobber-Zug
bräuchte `os.link` + `unlink` (schlägt mit `EEXIST` fehl) statt `os.replace`; das ist ein anderer
Zug mit anderen Dateisystem-Voraussetzungen und keine Formulierungsfrage. Diese Runde hat ihn nicht
gebaut, und der Eintrag behauptet nicht, dass er nicht nötig wäre.

**Was stattdessen begrenzt:** die Spanne ist **innerhalb einer Sitzung nicht erreichbar** —
`gate_write_scope` verweigert jeden Werkzeug-Schreibzugriff unter `project_memory/` außerhalb von
`staging/`, und `legacy/` ist kernel-geschrieben, also kann kein Aufrufer der Sitzung dort in dieser
Spanne etwas anlegen; erreichbar ist sie für einen zweiten Prozess oder einen Editor außerhalb der
Sitzung. Der Fall, dass beim **Planen** schon etwas dort liegt, ist vollständig abgedeckt: der
Trockenlauf meldet ihn vorab (`occupied_landings`), und der Lauf fragt unmittelbar vor der
Zugschleife noch einmal.

**Stolperdrähte:**
`test_migrate.test_the_move_replaces_a_file_that_appears_between_the_question_and_the_write`
(die Spanne selbst) und
`test_migrate.test_the_move_asks_again_when_the_place_was_free_while_the_plan_was_built`
(die Hälfte, die abgedeckt ist)

### L31 — „Wer hat die Datei geöffnet" ist der erste Rahmen außerhalb der Standardbibliothek

**Mechanismus:** die Zusicherung „jeder Lesezugriff dieses Moduls unter der Zustandswurzel geht
durch `_read_bytes`" wird an einem `sys.addaudithook` gemessen: beim `open`-Ereignis wird der Stapel
nach außen gegangen, und der **erste Rahmen außerhalb der Standardbibliothek** gilt als der, der die
Datei wollte. Öffnet eine Bibliothek, die nicht zur Standardbibliothek gehört, eine Zustandsdatei im
Auftrag dieses Moduls, wird der Vorgang ihr zugerechnet und ist im Ergebnis unsichtbar.

**Kette (gemessen 2026-08-09 im Klon außerhalb des Repos):** die Regel davor zählte `ast.Call` mit
`func.id == "open"` und war in **beiden** Richtungen falsch — ein echter zweiter, ungehandelter
Leser (`io.open` in `_retire_absorbed_documents`) ließ sie **grün**, eine verhaltensgleiche
Umschreibung innerhalb `_read_bytes` machte sie **rot** mit einer dann unwahren Meldung. Die neue
Messung ist in beiden Fällen richtig (rot / grün) und sieht zusätzlich `pathlib.Path.read_bytes`,
`codecs.open` und `os.open`. Was sie nicht sieht, ist der Fall oben.

**Der zweite Rest, und er ist der größere:** die Messung ist total über die **Schreibweise** und nur
über den Pfad, den **dieser eine Lauf** ausführt. Ein zweiter Leser in einem nie betretenen Zweig ist
hier grün — die abgelöste AST-Regel hätte ihn gefunden. Deshalb steht die statische Regel seit dieser
Runde **wieder daneben**, in der anderen Richtung:
`test_migrate.test_nothing_but_these_functions_can_name_a_file_of_the_state_directory`
liest die ganze **Datei** und fragt, welche Funktionen einen Pfad unter der Zustandswurzel überhaupt
**benennen** können — einen Schritt vor jedem Öffnen, also ohne Aufzählung von Öffner-Namen.
(Hier stand bis 2026-08-09 eine Deckungszahl „439 von 819 Anweisungszeilen". Sie stand an drei
Orten, nannte ihre Zählregel nicht — der Prüfer kam mit seiner eigenen auf 496 von 890 — und kein
Test hielt sie. Sie ist ersatzlos weg; was sie belegen sollte, ist jetzt die Zusicherung unten.)

**Die Korrektur dieser Runde, und sie war ein echtes Loch:** die statische Regel sieht nur, wer einen
Pfad **benennt**. Eine Funktion, die einen fertig komponierten Pfad **entgegennimmt**, benennt nichts
— `_unreadable_because(exc, path)` und `_without_path(text, path)` waren genau diese Form, lagen im
Fehlerzweig, und ein **echter zweiter Leser** in der ersten ließ **beide** Stolperdrähte grün
(gemessen 2026-08-09 im Klon außerhalb des Repos: beide Wächter rc 0, ganze Datei 125 passed,
Audithook meldete den Leser trotzdem nicht als Verletzung). Beide nehmen jetzt `rel` und komponieren
selbst, stehen damit wieder vor der Regel, und eine dritte Zusicherung im selben Test hält die
Eigenschaft statt der Liste: **kein Aufruf dieses Moduls reicht einen komponierten Zustandspfad an
eine andere Funktion desselben Moduls weiter** (`_handed_a_finished_path`).

**Urteil: OFFEN als Rest der Messung, kein Loch im Produkt.** Die Fremdbibliothek-Zurechnung
erreicht heute nichts: `yaml` ist die einzige Fremdbibliothek auf diesem Pfad, und ihr werden Bytes
übergeben, nie ein Pfad. Eine Aufzählung der erlaubten Zwischenschichten wäre wieder die Aufzählung,
gegen die dieses Repo gebaut ist.

**Was stattdessen begrenzt:** die Gegenrichtung läuft im selben Test mit — ein absichtlich
eingesetzter zweiter Leser in einem Rahmen von `migrate.py` **muss** gemeldet werden, sonst ist der
Test rot; und der Test verlangt, dass der Lauf überhaupt Zustandsdateien durch `_read_bytes`
geöffnet hat, damit „keine Verletzung" nicht heißt „es wurde nichts gelesen". Dass die beiden Regeln
sich in der Mitte treffen, ist seit dieser Runde **keine Prosa mehr, sondern eine Zusicherung
desselben Tests**: derselbe Prozess sammelt per `sys.settrace`, welche Funktionen er betreten hat,
und **jede** Funktion, die die statische Regel lizenziert, muss darunter sein. Was nach beidem
bleibt, ist ein zweiter Leser **innerhalb** einer lizenzierten Funktion, in einem Zweig, den der Lauf
nicht betritt.

**Stolperdraht:**
`test_migrate.test_every_state_file_this_module_opens_it_opens_through_read_bytes`

### L32 — Der Ablagename ist injektiv, weil er nie kürzt — und wird darum irgendwann unanlegbar

**Mechanismus:** `migrate.deposit_of` kodiert den ganzen Quellpfad in den Dateinamen und kürzt ihn
nie; genau das macht zwei Quellen zu zwei Namen (DEC-0024). Der Preis ist die Länge: `staging/` +
`v1-deposit--` + Quellpfad, kodiert in `migrate._NAME_ALPHABET` — jedes Zeichen, das nicht
Kleinbuchstabe, Ziffer, `-` oder `_` ist, wird zu einem `%xx`-Tripel in Kleinhex. Seit TSK-0023
Runde 6 gehört der **Großbuchstabe** dazu (F2: sonst faltet dieses Dateisystem zwei Ablagenamen zu
einem), er kostet also drei Zeichen statt einem. Ein Quellpfad, den das Dateisystem noch annimmt,
kann damit einen Ablagenamen erzeugen, den es nicht mehr annimmt.

**Kette (gemessen 2026-08-09 auf diesem Host):** die längste anlegbare Namenskomponente ist **255**
Zeichen, 256 antwortet `OSError: [Errno 22] Invalid argument`. Eine Quelldatei aus **248** ASCII-
Zeichen wird angelegt, ihr Ablagename ist **262** Zeichen lang und ist nicht anlegbar. Nicht-ASCII
trifft es früher, weil jedes Zeichen zu drei oder mehr Prozent-Tripeln wird: **29 CJK-Zeichen**
ergeben 235, **43 kyrillische** 247 — die nächste Handvoll darüber liegt jenseits der Grenze. Bis zu
dieser Runde druckte der Trockenlauf die Anweisung wortlos, und der Leser traf die Verweigerung des
Dateisystems statt einen Satz im Bericht.

**Urteil: OFFEN, nicht schließbar ohne den Defekt zurückzuholen, gegen den die Konstruktion gebaut
ist.** Kürzen oder Hashen macht aus zwei Quellen wieder einen Platz — das ist die Kollision, wegen
der DEC-0024 überhaupt eine Konstruktion statt einer Klausel verlangt. Ein zweistufiger Name
(Unterverzeichnis pro Quellverzeichnis) verschiebt die Grenze, macht die Ablage aber zu einem
**Verzeichnis** unter `staging/` — und das ist ein Staging-Schlüssel, den beide Leser als verwaist
melden. Diese Runde hat keinen dritten Weg gebaut und behauptet nicht, dass es keinen gibt.

**Was stattdessen begrenzt:** die Meldung sagt es jetzt dort, wo sie den Namen druckt
(`migrate.deposit_note`): um wie viele Zeichen der Name zu lang ist, dass dieses Dateisystem ihn
nicht nimmt, und dass dieses Kommando keinen kürzeren anzubieten hat und warum. Die Richtung des
Restes ist die harmlose: die Anweisung ist **nicht ausführbar**, nicht etwa ausführbar mit
Datenverlust — der Leser verliert nichts, er bekommt keinen Platz. Und die Grenze selbst steht an
genau einem Ort im Code (`migrate._NAME_MAX_CHARS`), gekoppelt an das Dateisystem statt
nacherzählt: der Stolperdraht legt die Namen wirklich an und verlangt, dass der Satz genau dann
erscheint, wenn das Anlegen scheitert — auf einem Host mit anderer Grenze wird er rot, und das ist
die richtige Antwort.

**Dieselbe Grenze trifft den Overflow-Namen 67 Zeichen früher, und dort ist die Folge größer:**
`migrate.overflow_deposit_of` (L35) kodiert nicht nur den Pfad, sondern Pfad **plus** sha256 — das
sind `%2f` und 64 Hex-Zeichen, gemessen 2026-08-09 als Differenz der beiden Namen für denselben Pfad
(`deposit_of` 37 Zeichen, `overflow_deposit_of` 104). Die Kette oben („248 ASCII → 262") liegt für
diesen Namen also 67 Zeichen früher; die blockierende Bedingung ist ein **belegter** Landeplatz unter
`legacy/`, dessen Pfad plus 67 über `_NAME_MAX_CHARS` geht. Was den Unterschied ausmacht, ist nicht
die Länge, sondern der Preis: ein unanlegbarer Datensatz-Ablagename kostet den Bulk **eines
Datensatzes**, ein unanlegbarer Overflow-Name hängt an `occupied_landings` — und solange der
Landeplatz belegt ist, ist `plan_is_executable` **falsch**, die Migration also durch keine der
gedruckten Routen mehr abschließbar. Seit BUG-0026 trägt auch `migrate.record_deposit_of` den
sha256 des Datensatz-Körpers im Namen (aus demselben Grund wie der Overflow-Name: die zugehörige
Abhilfe kürzt die Quelle, ein belegter Name muss also byte-gleiche Bytes tragen), liegt seine
Längengrenze also dieselben 67 Zeichen früher. Rest und nicht Blocker, weil die Ausfallrichtung
dieselbe harmlose ist wie oben (die Anweisung ist nicht ausführbar, sie verliert nichts) und
`deposit_note`
auch hier an der Druckstelle steht — `copy_instruction` ist der eine Komponist für beide Namen, der
Satz erscheint also für den Overflow-Namen genauso (gemessen: „That name is 40 character(s) longer
than the 255 …" für einen 200-Zeichen-Landeplatz).

**Ein weiterer Rest im selben Eintrag, weil er dieselbe Grenze betrifft:** `migrate.deposit_note`
misst nur die **Namenskomponente**, nicht den Gesamtpfad. Auf einem Host ohne Langpfad-Unterstützung
kann ein Name unter 255 Zeichen die Gesamtpfadgrenze sprengen, und dann fehlt der Satz genau dort,
wo er gebraucht wird. **Auf diesem Host nicht erreichbar** (gemessen 2026-08-09, in einem
Verzeichnisbaum außerhalb dieses Repos: Gesamtpfade von 261, 271, 321, 401, 451 und 520 Zeichen
werden alle angelegt, Namenskomponente jeweils unter 255). Nicht gebaut, weil die Grenze, die dann
gälte, auf diesem Host nicht messbar ist — und eine Zahl, die niemand hier messen kann, wäre genau
die nacherzählte Konstante, gegen die der Absatz darüber argumentiert.

**Stolperdraht:**
`test_migrate.test_a_deposit_name_too_long_to_create_says_so_where_it_is_printed`
(die Namenskomponente; für den Gesamtpfad gibt es keinen, siehe Absatz darüber)

### L33 — Eine Abhilfe, deren Ortsangabe erst zur Laufzeit entsteht, liest die statische Regel nicht

**Mechanismus:** `test_migrate.test_no_remedy_literal_this_repo_ships_names_a_place_inside_a_state_directory`
liest **Zeichenketten-Literale** des ausgelieferten Codes (`_remedy_literals`) und fragt jedes Wort
darin, ob es pfadförmig ist und eine Komponente im Zustandsverzeichnis nennt
(`_places_inside_a_state_directory`). Eine Abhilfe, die ihren Ort über einen **Formatplatzhalter**
einsetzt, hat im Literal kein solches Wort — der Ort entsteht erst beim Formatieren, und `%s` nennt
nichts.

Zwei weitere Formen fallen aus derselben Domäne, beide gemessen und beide **keine** Backtick-Frage
mehr: eine Abhilfe, die als **Name** statt als Literal übergeben wird
(`report.validate_state` reicht seit Runde 9 `migrate.THE_ONLY_UNLISTABLE_STEP` durch — die Zählung
der Parameter-Hälfte fiel dadurch von 57 auf 56), und eine, deren Empfänger unter einer Schreibweise
steht, die die Signaturauflösung nicht kennt (Alias, Attribut eines Objekts, umbenennender Import).
Die Backtick- und Leerzeichenbedingung, die bis Runde 7 hier stand, gehört **nicht mehr** zu dieser
Regel: sie sitzt in `_state_paths_in`, dem Leser des **Laufzeit**-Tests
(`test_no_remedy_the_validator_prints_names_a_place_inside_the_state_directory`), und dort wertet
`if " " in word.strip(): continue` ein Wort mit Leerzeichen weiterhin als Befehlszeile statt als
Pfad.

**Kette (gemessen 2026-08-09):** zwei solche Abhilfen existieren heute, beide nennen einen Ort im
Zustandsverzeichnis und schlagen eine **überschreibende** Bewegung darauf vor:

- `team-kits/kernel/state.py` — `corrupt item file for %s at %s … Remedy: \`git restore %s\``
- `team-kits/kernel/approvals.py` — `… Remedy: re-approve the current revision, or \`git restore %s\`
  to return to the approved content` — dort ist das Verwerfen der Nutzerbearbeitung ausdrücklich der
  Zweck.

Beide sind für die statische Regel unsichtbar; der Trockenlauf-Test daneben
(`test_no_remedy_the_validator_prints_names_a_place_inside_the_state_directory`) sieht nur, was seine
Fixtures erreichen, und erreicht keine der beiden.

**Urteil: OFFEN als Rest, nicht blockierend.** Die Kette läuft **nicht innerhalb einer Sitzung**
durch, und das ist gemessen statt geschlossen: die gedruckte Zeile selbst, als echter Hook-Prozess
mit JSON auf stdin, 2026-08-09 —

```
gate_lead_write_scope (dieses Repo)  git restore project_memory/tasks/active/TSK-0023.yaml  -> rc 2
gate_write_scope (dev/office/research, je frisch scaffoldetes Projekt)
                                     git restore project_memory/product/active/PR-0001.yaml  -> rc 2
```

Der Leser muss also eine Shell **außerhalb** der Sitzung öffnen. Und anders als bei DEC-0024 ist die
vorgeschlagene Bewegung im Fall von `approvals.py` genau das, was der Nutzer will.

**Was stattdessen begrenzt:** der Name des Tests und sein erster Satz sagen **LITERAL** statt „jede
Zeichenkette, die der ausgelieferte Code drucken kann", und sein Docstring nennt die beiden Stellen.
Die Behauptung deckt damit genau die Domäne, die die Regel wirklich liest; vorher behauptete sie
eine, die sie nicht hatte. Die Domäne selbst ist seit Runde 9 dreiteilig — Wort, `remedy`-Slot und
**Positionsargument, das in einem `remedy`-Parameter landet** — und die dritte Hälfte hat allein 56
Literale, darunter alle Befunde von `report.validate_state`.

**Stolperdraht:** keiner für die Laufzeit-Hälfte. Für die Literal-Hälfte:
`test_migrate.test_no_remedy_literal_this_repo_ships_names_a_place_inside_a_state_directory`

### L34 — Ein Empfänger, zu dem die Namen dieses Moduls an der Verwendungsstelle nicht führen, ist für die Übergaberegel unsichtbar

**Mechanismus:** `test_migrate._handed_a_finished_path` sieht eine Übergabe genau dort, wo ein
Zustandspfad und ein **Name dieses Moduls** zusammentreffen — in einem Aufrufausdruck (beide Seiten
über die Locals verfolgt: `_carries_a_state_path` für den Pfad, `_value_leads_to` für den Empfänger)
oder in einer Ablage, deren Ziel in einem Modulnamen wurzelt (`_stashed_names`). Was übrig bleibt,
ist ein Empfänger, zu dem diese Namen **an der Stelle, an der er benutzt wird**, nicht führen.

Die Grenze „eigenes gegen fremdes Modul" war bis Runde 8 die Beschreibung dieses Rests und ist
gemessen **keine** Grenze: vier gewöhnliche Routen **innerhalb** dieser Datei trugen die Bytes in
einen echten Leser, während die Regel `[]` meldete (B1). Sie sind seither gedeckt. Und die
Beschreibung, die in Runde 8 an ihre Stelle trat — „der Rest ist ein Empfänger, zu dem die Namen
dieses Moduls **an der Verwendungsstelle** nicht führen" — ist **ebenfalls widerlegt**: die
Closure-Route unten führt in einen Empfänger, den `_module_own_names` sehr wohl kennt, und wird
trotzdem nicht gesehen, weil es überhaupt keinen Aufrufausdruck gibt, der etwas überträgt.

**DEC-0029 ist die Konsequenz daraus und gilt für diesen ganzen Eintrag:** die Regel wird als
**Menge gemessener Routen** geführt (heute sechzehn im Korpus, fünf hier als offen benannt), nicht
als Deckung. Ob ein Wert in beliebigem Python eine Stelle erreicht, ist statisch nicht entscheidbar;
der Verlauf 6 → 12 → 16 → 17 ist genau das von innen gesehen.

**Kette (gemessen 2026-08-09, echter Prozess, Markerdatei, Leser gibt die gelesenen Bytes zurück):**
in `_read_bytes` gepflanzt —

```
os.environ["PARKED"] = _state_path(state, rel)      # Ablage in einem fremden Modulobjekt
_a_reader_of_a_foreign_module()                     # liest open(os.environ["PARKED"], "rb")
parked in an object of ANOTHER module               reads: YES   rule says: []

reader = _a_reader_factory()                        # Aufrufergebnis DIESES Moduls ...
functools.partial(reader, _state_path(state, rel))()   # ... als ARGUMENT an einen fremden Wrapper
out of a factory, handed to a foreign wrapper       reads: YES   rule says: []
```

Und die Route, die der Prüfer in derselben Prüfung fand, in der Runde 8 die sechzehnte einbaute — ein
`def` **innerhalb** der Wirtsfunktion, der den Pfad aus der **Closure** liest statt ihn als Argument
zu bekommen. Hier nachgemessen (2026-08-09, dieselbe Vorrichtung, echter Prozess; der Leser meldet
sich über eine **Markerdatei**, weil der Kanal die Antwort mitentscheidet — siehe direkt darunter):

```
path = _state_path(state, rel)
def _a_closure_reader():                              # kein Argument, kein Aufrufausdruck ...
    open(r"<marker>", "wb").write(open(path, "rb").read())   # ... liest aus der Closure
_a_closure_reader()
into a def that closes over the path        reads: YES   rule says: []   handed: []
```

**Und was dabei auffiel, gemessen im selben Lauf:** dieselbe Route wird **doch** gemeldet, sobald der
geschachtelte Leser seine Bytes an irgendeinen Namen dieses Moduls weiterreicht
(`_PLANTED.append(open(path, "rb").read())` → `handed: [('_read_bytes', 'path', '_PLANTED', 766)]`,
und ebenso mit einem Zwischen-Local). Das ist kein Schutz, sondern ein Zufall der Beobachtung: was
die Regel dort sieht, ist der **Aufruf, der die Bytes ablegt**, nicht die Übergabe des Pfades. Ein
Leser, der über einen Kanal außerhalb dieses Moduls meldet, ist unsichtbar — und genau das ist die
Route.

Die zweite Route ist der Preis der Asymmetrie, die B1 an die Verwendungsstelle gehängt hat: ein
Aufrufergebnis dieses Moduls zählt nur in der **Callee-Position** als Code dieses Moduls, weil dort
das Programm selbst sagt, dass der Wert aufrufbar ist. In der Argumentposition dieselbe Auflösung zu
fahren, meldet das ausgelieferte Modul mit `absorbed_documents` als Empfänger eines Pfades, den es
nie bekommt (gemessen, dieselbe Runde). Ebenfalls offen und derselben Klasse: ein Empfänger aus
`sys.modules` oder `getattr`, und ein Aufrufausdruck, der sich auf gar keinen Namen reduzieren lässt
(ein sofort angewandtes Lambda).

Zum Vergleich, im selben Lauf: **jede** Route des Korpus (`_HOW_A_PATH_TRAVELS`) — darunter die
Ablage in Attribut, Mapping, Liste und **Default-Argument** dieses Moduls, der lokale Alias des
Empfängers, deren Kreuzung, und ein `def` innerhalb der Wirtsfunktion, **der den Pfad als Argument
bekommt** — wird benannt.

**Urteil: OFFEN als Rest, nicht blockierend (DEC-0022 zum Bedrohungsmodell dieser Regel, DEC-0029
zur Anspruchshöhe).** Die Regel ist ein Stolperdraht gegen einen **zweiten Leser**, den ein Autor
dieses Moduls versehentlich hinzufügt; sie ist keine Sandbox gegen einen Autor, der ihn verstecken
will. Ein Pfad, der durch `os.environ` reist, und ein Fabrikergebnis, das durch einen fremden
Wrapper zurückgereicht wird, sind keine Schreibweisen, in die man hineinfällt — die Closure-Route
dagegen **schon**, und sie bleibt trotzdem offen: sie zu sehen hieße, Datenfluss ohne Übertragung zu
verfolgen, und genau davor endet die statische Frage.

**Was stattdessen begrenzt:** der eigentliche Schutz ist nicht dieser Draht.
`test_every_state_file_this_module_opens_it_opens_through_read_bytes` läuft mit einem Audithook und
sieht **jedes** Öffnen einer Datei unter der Zustandswurzel, egal wie der Pfad dorthin kam und egal
wie das Öffnen geschrieben ist. Was **dieser** Wächter nicht sieht, gehört ausdrücklich daneben: er
misst nur, was ein Lauf wirklich ausführt, und ist für jeden nicht betretenen Zweig blind — die
umgekehrte Hälfte des statischen Drahts. Dazu schreibt der Docstring von `_handed_a_finished_path`
den **Mechanismus** hin statt einer Liste gedeckter Schreibweisen und nennt alle fünf offenen Formen
beim Namen.

**Stolperdraht:** keiner für diese fünf Routen (das ist das Loch). Für die gedeckten:
`test_migrate.test_the_rule_against_handing_a_state_path_on_follows_the_value_and_not_the_call_shape`

### L35 — Eine gedruckte Abhilfe verlangte eine Bewegung ohne Ziel — GESCHLOSSEN durch ein konstruiertes Ziel außerhalb des Zustandsverzeichnisses (Runde 9)

**Mechanismus (was hier stand):** DEC-0024 hat zwei Klauseln. Die erste verbietet, einen Platz **im**
Zustandsverzeichnis zu nennen, den der Leser anlegen oder überschreiben müsste. Die zweite verlangt
**Kopieren statt Verschieben**, „also kann kein befolgter Rat etwas vernichten, **auch nicht die
Quelle**". Genau **eine** ausgelieferte Abhilfe verlangte weiterhin eine Bewegung: die des **belegten
Landeplatzes** im Trockenlauf (`team-kits/kernel/migrate.py`, Abschnitt *LANDING PLACE UNDER legacy/
ALREADY TAKEN*). Sie nannte kein Ziel — die Wahl lag beim Leser — aber sie nahm die Quelle weg:

```
migrate.render, belegter Landeplatz   "Remedy, per document: take the file each line above names
                                       on the right out of the state directory, from a shell
                                       outside the session, then re-run the dry run."
                                      nennt ein Ziel: nein     verlangt eine Bewegung: ja
```

Was der Leser bewegt, ist eine Datei unter `legacy/` — ein kernel-geschriebener Bereich, in dem eine
frühere Migration ihr Ergebnis abgelegt hat. Wer sie irgendwohin schiebt und dort vergisst, verliert
sie; das Decision-Item des früheren Laufs trägt nur ihren Hash, nicht ihren Inhalt.

**Entscheidung des Nutzers (2026-08-09): Ziel konstruieren.** Nicht die Ausnahme abnehmen und nicht
den Vorschlag streichen, sondern ein **konstruiertes, kollisionsfreies Ziel außerhalb des
Zustandsverzeichnisses** nennen — so wie `deposit_of` es innerhalb von `staging/` tut, nur außerhalb.
Die frühere Begründung („das Werkzeug darf kein Ziel ableiten") betraf Ziele **im** Zustandsbaum; für
ein Ziel daneben gilt sie nicht.

**Was gebaut ist:** `migrate.overflow_deposit_of(rel, digest)` — `../v1-legacy-overflow/` neben dem
Zustandsverzeichnis, darunter ein Name aus demselben Kodierer wie `deposit_of` (`_encoded_name`,
`migrate._NAME_ALPHABET`), der den **Landeplatzpfad und den sha256 des dort stehenden Inhalts** trägt.
Der Abschnitt druckt pro Zeile den einen Composer (`copy_instruction`) und danach den zweiten Schritt:
erst **kopieren**, dann — und nur dann — das Original entfernen.

```
  a.yaml                       -> legacy/a.yaml is already taken
     Remedy: COPY it -- the original stays where it is -- to
     `../v1-legacy-overflow/v1-deposit--legacy%2fa%2eyaml%2f3d51709d…`. Then, and only once that
     copy exists, remove legacy/a.yaml itself from a shell outside the session -- the copy is what
     keeps the file, and removing the original is what frees the place.
```

**Warum der Inhalt im Namen steht und nicht nur der Pfad** — das ist der Unterschied zu `deposit_of`
und eine gemessene Kette, keine Vorsicht: dort bleibt die Quelle stehen, ein belegter Name hält also
eine frühere Kopie **derselben** Datei. Hier entfernt der Leser das Original, und derselbe
Landeplatzpfad kann später andere Bytes tragen (Lauf 1 legt A ab; Leser kopiert A heraus und löscht
es; Lauf 2 legt B am selben Platz ab; Lauf 3 bietet dieselbe Abhilfe wieder an). Mit dem Pfad allein
im Namen landet die dritte Anweisung auf A. Mit dem Digest darin ist ein belegter Name eine Datei mit
**identischen Bytes**.

**Urteil: GESCHLOSSEN.** Ausgeführt und gemessen, nicht behauptet:
`test_migrate.test_the_place_a_taken_landing_is_freed_to_is_named_and_lies_outside_the_state_directory`
fährt beide Schritte auf der echten Platte — die Kopie ist byte-gleich, der Landeplatz danach frei,
der nächste Plan ausführbar — und lässt anschließend eine **zweite** Datei denselben Platz belegen:
die zweite Anweisung nennt einen anderen Namen, und die erste Kopie steht danach unverändert da.

**Was offen bleibt und hier benannt statt geschlossen wird:** zwei weitere Abhilfen von
`report.validate_state` sagen weiterhin *take the file out of the state directory* (`_bounded` für ein
Dokument über einem der beiden Lesebudgets, und die Abhilfe für ein unparsbares Dokument). Sie nennen
**kein** Ziel, überschreiben also nichts; sie können aber die Quelle kosten. Warum die hier gebaute
Konstruktion an beiden Stellen fehlt, ist **nicht derselbe Grund** — bis Runde 10 stand hier einer für
beide („diese Stellen lesen die Datei absichtlich nicht"), und für die zweite war er falsch:

- **`_bounded` — nicht verfügbar.** Der Name braucht den sha256 der Datei, und dieser Zweig
  entscheidet allein aus `os.path.getsize`, **vor** jedem Lesen — genau weil das Lesen es ist, was
  `DOCUMENT_MAX_BYTES`/`DOCUMENT_SCAN_MAX_BYTES` auf dem Pfad des Merge-Gates verbieten. Ein Digest
  wäre hier nur zum Preis des unbegrenzten Lesers zu haben, gegen den der Bund gebaut ist.
- **Unparsbares Dokument — verfügbar und nicht gebaut.** Dieser Zweig wird erst hinter `spent += size`
  erreicht, über `migrate._read_document` → `_read_bytes`; der Parse scheitert **nach** dem Lesen, die
  Bytes waren also in der Hand. Gemessen 2026-08-09 mit `sys.addaudithook` über einen echten
  `report.validate_state`-Lauf außerhalb dieses Repos: geöffnet wurden `.kernel.lock`, das Wurzelitem
  und `broken.yaml`, **nicht** aber das übergroße `big.yaml`. Der Digest hätte hier keinen einzigen
  zusätzlichen Byte-Zugriff gekostet. Was fehlt, ist der Rückweg — `_read_document` gibt die Bytes
  nicht heraus, und ein Ziel anzubieten kostet eine Signaturänderung an einem Leser mit fünf
  Aufrufstellen. Nicht gebaut; das ist ein Rest und keine Unmöglichkeit.

Dazu der Unterschied, der beide von dieser Fundstelle trennt: was sie bewegen lassen, ist ein Dokument,
das der Leser **selbst geschrieben** hat, während unter `legacy/` eine Datei liegt, für die es nach
der Installation keinen Schreiber mehr gibt. Ein Rest, kein Blocker — die Kette braucht eine Shell
außerhalb der Sitzung und die Unachtsamkeit des Lesers mit seiner eigenen Datei.

**Und ein dritter Rest, in der geschlossenen Abhilfe selbst:** der Zusatz *from a shell outside the
session* hängt in `migrate.py` (Abschnitt *LANDING PLACE UNDER legacy/ ALREADY TAKEN*) am
**Entfernen**; der **Kopie** ist keiner beigegeben, obwohl auch sie an diesem Gate vorbei muss. Gemessen
2026-08-09 gegen den ausgelieferten `gate_write_scope.py` als Prozess, in einem gescaffoldeten Projekt
außerhalb dieses Repos mit gültigem Wurzelitem: `cp`, `cp -p` mit absolutem Ziel, `Copy-Item` (relativ
und absolut) und `python -c "shutil.copy(...)"` antworten **rc 2**, das Entfernen (`rm`,
`Remove-Item`) ebenfalls rc 2, reines Lesen rc 0. Der fehlende Halbsatz wäre aber **nicht pauschal
wahr**, und deshalb steht er hier statt eingesetzt im Code: eine Umleitung, die die Quelle nur liest
und außerhalb landet (`cat < project_memory/legacy/a.yaml > ../v1-legacy-overflow/<name>`,
`Get-Content … > …`), antwortet **rc 0** — diese eine Schreibweise der Kopie gelingt in der Sitzung.
Ausfallrichtung harmlos: wer die Kopie mit einem Kopierbefehl versucht, bekommt eine Verweigerung, die
der Satz nicht ankündigt, aber keinen Verlust. Fix wäre ein Halbsatz an derselben Stelle, der die
Verweigerung nennt, ohne sie für jede Schreibweise zu behaupten.

**Was stattdessen begrenzt:** die Datei, die der Leser bewegt, ist im selben Abschnitt **beim Namen
genannt** (linke und rechte Spalte je Zeile), und der Abschnitt sagt, warum sie dort steht. Dazu die
Domäne des DEC-0024-Stolperdrahts: seit Runde 9 sind es **drei** Arten, wie dieses Repo eine Abhilfe
ausliefert — das **Wort** `Remedy` (225 Literale), der `remedy`-Slot als Schlüsselwort (92) und das
**Positionsargument, das in einem `remedy`-Parameter landet** (56, darunter alle Befunde von
`report.validate_state`) — und die Ortsangabe wird backtick-unabhängig über **alle** Pfadkomponenten
gelesen, jetzt auch bei einem Wort, dessen einziger Trenner am Ende steht (`evidence/`).
Der Spec-Satz in `docs/HARNESS_V2_SPEC.md` (e2) behauptet nicht, der Vorlauf schlage „keine Bewegung"
vor, sondern er leite **kein Ziel im Zustandsbaum** mehr ab.

**Stolperdraht:** für die Ortsangabe
`test_migrate.test_no_remedy_literal_this_repo_ships_names_a_place_inside_a_state_directory`;
für die geschlossene Bewegung
`test_migrate.test_the_place_a_taken_landing_is_freed_to_is_named_and_lies_outside_the_state_directory`;
für die unlistbare Hälfte
`test_migrate.test_the_remedy_for_a_directory_nobody_can_list_offers_no_step_that_moves_it`;
für die Eigenschaft, auf der die Trennung der beiden Reste ruht — welches der beiden Dokumente ein
Lauf öffnet und welches nicht —
`test_migrate.test_the_two_remedies_that_still_move_a_file_differ_in_whether_the_file_was_read`
(rot in beide Richtungen gemessen, siehe `docs/reviews/2026-08-08-tsk0023-measurements.md`, R10.1);
für die Reste selbst keiner.

### L36 — Ein kanonisches Verzeichnis, das niemand auflisten kann, las sich für die Gates wie „noch kein Wurzelitem" — GESCHLOSSEN (Runde 9)

**Mechanismus:** `_root.has_root_item` (in allen drei Kits) beantwortete die Frage „hat dieses Projekt
schon ein Wurzelitem?" mit `glob.glob` über `project_memory/**`. `glob` meldet ein Verzeichnis, das
es nicht öffnen kann, als **leer** — ohne Fehler. Die Antwort war dann `False`, und fünf Gates lesen
`False` als „das Projekt wird noch eingerichtet, wir gelten nicht". Ein Verzeichnis, das niemand
lesen kann, schaltete also genau die Gates ab, die das Wurzelitem schützen.

**Kette (gemessen 2026-08-09, echter Hook-Prozess, JSON auf stdin, Zustand außerhalb dieses Repos):**

```
product/active/ lesbar        gate_git.py "git merge feat/PR-0001-x"   -> rc 2 (verweigert)
product/active/ nicht listbar gate_git.py "git merge feat/PR-0001-x"   -> rc 0 (durch)   [vorher]
product/active/ nicht listbar gate_git.py "git merge feat/PR-0001-x"   -> rc 2           [nachher]
```

**Das Urteil bis Runde 8 war „OFFEN als Rest", und es war falsch.** Es stützte sich darauf, dass die
Rechteänderung aus der Sitzung heraus nicht erreichbar sei — `gate_write_scope` verweigert vier
naheliegende Zeilen (`icacls` in zwei Schreibweisen, `chmod`, `attrib`; alle rc 2, gemessen). Der
Prüfer hat das umgangen, und der Mechanismus stand als `L4` („Schreibverben innerhalb einer
Programmsprache … bewusst nicht geschlossen") zwei Bildschirmseiten weiter oben in derselben Datei:

```
python -c "import os,subprocess;p=os.path.join('project'+'_memory','product','active');
           subprocess.run(['icacls',p,'/deny','zenti:(RD,RA)'])"
alle acht Bash-Hooks rc 0  ->  die Zeile läuft  ->  gate_git rc 2 wird rc 0
```

Zweite Route ohne `-c`: `Write scripts/deny_it.py` (alle Schreibhooks rc 0 außer `guard_pm_scope`,
das die PM-Rolle betrifft), dann ausführen. Die Kette läuft damit **innerhalb einer Sitzung** durch
und ist blockierend.

**Fix:** ein Verzeichnis, das existiert und nicht auflistbar ist, ist **nicht** „noch kein
Wurzelitem". `has_root_item` listet jetzt selbst (`_root._names_matching`) und kennt drei Antworten
statt zwei: Namen gefunden, nichts da (nicht vorhanden oder kein Verzeichnis), und **keine Antwort**
— jeder andere `OSError`. Der dritte Fall zählt als Wurzelitem, weil die beiden Ausfallrichtungen
nicht symmetrisch sind: „kein Item" schaltet fünf Gates ab, „ein Item" kostet in einem Projekt, das
noch eingerichtet wird, eine Verweigerung — und eine Verweigerung sagt es.

**Stolperdraht:**
`test_migrate.test_the_remedy_for_a_directory_nobody_can_list_offers_no_step_that_moves_it`
misst beide Seiten mit dem ausgelieferten `gate_git.py` als echtem Prozess: `rc 2` bei lesbarem
Verzeichnis und `rc 2` bei unlesbarem. Fällt der Prädikat auf `glob` zurück, wird dieser Test rot.

### L37 — `validate_state` stürzt über ein kanonisches Verzeichnis, das es nicht auflisten kann

**Mechanismus:** `report._iter_active` läuft über `ProjectState.iter_active_items`, und das ruft
`os.listdir` ohne `onerror`-Behandlung. Ein kanonisches Verzeichnis ohne Leserecht liefert dort einen
ungefangenen `PermissionError`, statt ein Finding zu erzeugen. `migrate.search_coverage` behandelt
denselben Fall (`onerror` → `UNLISTABLE`); der Validator tut es nicht.

**Kette (gemessen 2026-08-09, Zustand außerhalb dieses Repos, `product/active/` ohne Leserecht):**

```
migrate.search_coverage(state)   -> Zeile "product/active/  unlistable  ..."
report.validate_state(state)     -> PermissionError [WinError 5] ... \project_memory\product\active
```

**Urteil: OFFEN als Rest, nicht blockierend.** Ein Absturz ist **laut**: kein Aufrufer liest ihn als
„keine Befunde". Die Ausfallrichtung ist damit die harmlose — anders als bei `L36`, wo dieselbe
Ursache still durchließ. Der Auslöser ist derselbe wie dort, und er ist **innerhalb einer Sitzung
erreichbar** (die `python -c`-Kette bei `L36`); was diesen Eintrag trotzdem zum Rest macht, ist
allein die Richtung des Ausfalls, nicht die Unerreichbarkeit.

**Was stattdessen begrenzt:** der Vorlauf der Migration beantwortet dieselbe Frage über denselben
Zustand und tut es vollständig (`UNLISTABLE`, blockierend), und `report.validate_state` läuft in
jedem Kit hinter einem Hook, der einen Absturz als Verweigerung weitergibt statt als Freigabe.

**Stolperdraht:**
`test_migrate.test_the_remedy_for_a_directory_nobody_can_list_offers_no_step_that_moves_it`
verlangt den `PermissionError` ausdrücklich; wird der Fall zu einem Finding, wird der Test rot.

### L38 — Die Gate-Suite dieses Repos war rot, und keine Runde hat es bemerkt

**Mechanismus:** `.claude/hooks/test_gates.py` läuft **nicht** in `python -m pytest tools/` mit; sie
wird ausdrücklich gestartet (`python -B -m pytest .claude/hooks/test_gates.py -q`). Ein Rot darin
kommt also durch jede Abnahme, die nur die Werkzeugsuite fährt. Genau das ist passiert: der Ausfall
kam mit TSK-0022 herein und hat mindestens eine ganze Runde überlebt, ohne irgendwo zu stehen.

**Kette (gemessen 2026-08-09 vom Prüfer, isoliert reproduziert):** `1 failed, 142 passed`. Gefallen
ist die **Kontrolle** eines Sandkasten-Tests — der Host stellt den Unfall nicht mehr her, gegen den
der Test gebaut ist, also sagt nicht nur eine Zusicherung nichts, sondern der ganze Test.

**Urteil: OFFEN, und nicht dieser Runde zuzurechnen.** Die Ursache liegt in `.claude/`, dem
verbotenen Bereich von TSK-0023; diese Runde fasst dort nichts an. Der Befund ist als
`project_memory/bugs/active/BUG-0014.yaml` erfasst — mit Messung, Repro und den drei
Abnahmekriterien (Test misst wieder, Ursache benannt, ein Weg der ein Rot dieser Suite bemerkt).

**Was stattdessen begrenzt:** die Suite ist rot und nicht still — wer sie fährt, sieht es sofort;
und was sie misst, sind die Gates dieses Repos, deren Verhalten in Abschnitt 12 mit eigenen
Ketten steht. Bis BUG-0014 abgearbeitet ist, ist der Sandkasten-Test dieser einen Datei **keine**
Deckung, und keine Runde darf ihn als solche zitieren.

**Stolperdraht:** keiner in `tools/` — das ist der Kern des Eintrags. BUG-0014 AC-3 verlangt einen.

### L39 — Der Handover-Guard folgt nicht in die Verbposition, die eine Substitution oder ein ungelisteter Wrapper besetzt — und sein Marker ist nur beim Namen geschützt (TSK-0031, TSK-0032, eingeengt in Runde 3)

**Mechanismus:** `user/claude/hooks/handover_guard.py::_handle_shell` liest eine Bash-Zeile in
Schritten, deren **Reihenfolge tragend ist**, und nur diese sind gebaut: (1) **Here-Document-Körper**
werden auf dem **rohen** Text herausgeschnitten — dort ist der Delimiter noch als quotiert oder
unquotiert lesbar; (2) Zeilenfortsetzungen werden zusammengezogen (`_CONTINUATION`), (3) erst dann
läuft `_norm`, das sonst aus jedem `\` ein `/` macht und beides unsichtbar; (4) die Zeile wird an
**unquotierten** Trennzeichen zerlegt (`_SEPARATORS` = `;`, `&`, `|`, `\n`, `\r`; die Doppelformen
`&&`/`||`/`|&` brauchen keinen eigenen Eintrag, sie sind zwei Trenner mit einer leeren Spanne
dazwischen); (5) der Verb eines Teilbefehls ist sein erstes Wort, das ein Kommandoname ist —
`VAR=value`, ein führendes `(`/`{`, die **POSIX-Schlüsselwörter** eines zusammengesetzten Kommandos
und eine kleine Wrapper-Menge werden übersprungen, und nach einem `case`-Muster (`a)`) oder einem
Funktionskopf (`f()`) beginnt eine **zweite Namensposition** (`_name_positions`); (6) als **Lesen**
gilt ein Hilfs-Flag an beliebiger Stelle (gemessen: `kernel.cli --root project_memory capture
--help` endet rc 0, es kapturt nichts) und ein Lese-**Unterkommando** nur in Unterkommando-Position
— `capture doctor` ist damit kein Lesen mehr.

**Ein Here-Document-Körper gilt nur als Daten, wenn seine Delimiter-Zeile im selben Aufruf
tatsächlich vorkommt.** Das ist die Bedingung, die eine ganze Fehlerfamilie schließt: ohne sie hat
jedes `<<`, das gar keines ist, den **gesamten Rest ungeprüft** verschluckt — gemessen an einer
Arithmetik-Verschiebung (`echo $((1<<2))`), an einem `<<` in einem **Kommentar** und an einem
quotierten `<<EOF`, das der Unbalanciert-Rückfall der Quote-Maske wieder sichtbar machte. Ergänzend
wird `<<` nur an einer **Umleitungsgrenze** anerkannt (Zeilenanfang, Leerzeichen, Trenner) und ein
unquotierter Kommentar vorher abgeschnitten; beide tragen je einen eigenen roten Fall, nämlich den,
in dem das Falsch-Delimiterwort später **doch** als Zeile auftaucht.

**Was das NICHT liest, ist die Verbposition, die von etwas besetzt ist, dem dieser Leser nicht
folgt** — eine Klasse, mehrere Schreibweisen: eine Shell, die die Zeichenkette später ausführt
(`sh -c '…'`, `bash -lc '…'`); eine **Substitution**, die den Befehl erst erzeugt (`$(…)`,
Backticks, `<(…)` — **auch in doppelten Quotes eingebettet**, denn bash führt eine
Kommandosubstitution in `"…"` aus, während dieser Leser einer quotierten Spanne nicht folgt;
gemessen `echo "a $(python … capture) b"` rc 0, „quoted" heißt also **nicht** „sicher"); ein
**Starterwort außerhalb von `_WRAPPERS`** (`nohup`, `timeout 60`, `uv run`,
`xargs -I{}`, `eval`); und jede kodierte/verschleierte Form. `_WRAPPERS` ist die eine Aufzählung,
die hier nicht schließbar ist — jedes künftige Starterwort stellt sich ebenso davor —, und genau
darum steht sie hier als Rest statt als verlängerte Liste.

**Kette (gemessen 2026-08-10/11 unter Marker, isoliertes cwd außerhalb des Repos, echter Prozess):**
Vorher rc 0, jetzt rc 2 — die drei Fortsetzungsformen (`python \⏎ -m kernel.cli create-task`,
`python -m \⏎ kernel.cli …`, `PYTHONPATH=x python -B \⏎ -m kernel.cli … capture PR`) und acht
zusammengesetzte Kommandos (`for … do`, `while read … do`, `until … do`, `if … then`, `… else …`,
`(…)`, `{ …; }`, `! …`). Weiterhin rc 2 (Regression): `&&`, `||`, `;`, `|`, `|&`, `&`, `\n`, `\r`,
sowie eine Ableitung **nach** einem Heredoc-Ende und nach einer unbalancierten Quote.
Weiterhin rc 0 und **richtig so** — `sh -c '…'`, `bash -lc '…'`, `echo $(python … capture)`,
`echo \`python … capture\``, `diff <(python … capture) /dev/null`, `nohup/timeout 60/uv run/xargs
-I{}/eval python … capture`.

**Zwei Über-Verweigerungen sind mit demselben Rework verschwunden** (vorher rc 2, jetzt rc 0):
ein über eine Fortsetzung umgebrochener **Lesebefehl** (`python scripts/harness.py \⏎ doctor`,
`python -m kernel.cli \⏎ --help`) und ein Trenner **innerhalb von Quotes**
(`echo 'a; python … capture'`). Die Vorfassung dieses Eintrags nannte quotierte Trenner als
Durchlass — das war die falsche Richtung, gemessen war es eine Über-Verweigerung. Ebenso getroffen
war der **erlaubte Planweg**: `cat > project_memory/product/masterplan.md <<'EOF' … EOF` wurde
abgelehnt, weil der Heredoc-Körper als Befehl gelesen wurde; er gilt jetzt als Daten.

**Runde 3 hat vier weitere Durchlässe geschlossen, alle am laufenden Hook gemessen** (vorher rc 0,
jetzt rc 2): die drei Falsch-Heredocs oben; ein **quotierter** Delimiter, dessen Körper mit einem
Markdown-Zeilenumbruch (`\` am Zeilenende) endete — reales bash terminiert dort an `EOF` und führt
die Folgezeile aus, der Leser hatte sie durch sein zu frühes Zusammenziehen verloren; ein
`case`-Muster und ein Funktionskopf in Verbposition (`case x in a) python … capture;; esac`,
`f() { python … capture; }`); und ein **Lesewort an beliebiger Stelle**
(`python scripts/harness.py capture doctor`, `… capture --note "doctor"`), das die ganze Zeile
entwertete.

**Runde 4 hat drei Ränder desselben Reworks geschlossen, alle gemessen.** (R3-1) Endet die
`<<`-**Umleitungszeile selbst** auf einer Fortsetzung, überbrückte das nachträgliche Zusammenziehen
den Schnitt, den das Herausschneiden des Körpers gemacht hatte, und klebte die Ableitung ins
`cat`-Segment (`cat <<'EOF' \⏎ > …masterplan.md⏎…⏎EOF⏎python … capture`, vorher rc 0). Behoben,
indem der Körper durch **gleich viele Leerzeilen** ersetzt wird statt gelöscht — die Zeilenzahl
bleibt, der Join überspannt nichts. (R3-2) Ein `)` in der **Prosa eines quotierten Arguments**
öffnete eine zweite Namensposition, sodass `git commit -m "… (siehe Plan) … python … capture"`
fälschlich rc 2 war; die Tokenisierung respektiert jetzt Quotes, ein quotiertes Wort endet auf `"`
statt auf `)`. (R3-3) Ein Hilfs-Flag in einem **quotierten Wert** (`… capture --body "see --help
…"`) entwertete die Zeile — argparse sieht dort einen Wert, kein Flag; dieselbe quote-respektierende
Tokenisierung schließt das mit, weil `--help` dann kein eigenes Token mehr ist.

**Eine dritte Klasse kam aus dem RPG-Piloten und war bis dahin unbenannt: Selbstabschaltung über
die eigene Vorbedingung.** Der Guard prüft zuerst, ob `.claude/HANDOVER_PENDING` existiert; ist die
Datei weg, ist jeder weitere Aufruf ein No-op. Gemessen am laufenden Hook (Pilot, hier reproduziert):
`rm`, `rm -f`, `del`, `mv`, `Remove-Item`, `Move-Item`, eine Umleitung auf den Marker und die
gewrappte Form waren **alle rc 0**, und ein Produktcode-Write und ein Task-Spawn direkt danach
ebenso. **Gebaut ist jetzt:** ein Segment, das den Marker **beim Namen** nennt, wird verweigert,
sofern sein Verb nicht in einer kleinen **Lese-Allowlist** steht — die Aufzählung läuft hier
absichtlich andersherum als sonst in der Datei, ein unbekanntes Verb wird also **verweigert**, damit
ein nicht gelisteter Leser Reibung kostet und kein nicht gelisteter Entferner den Guard. Alle elf
Entfernungsformen sind jetzt rc 2; `cat`, `ls`, `Get-Content`, `grep`, `test -f` bleiben rc 0.
**Nicht gebaut, gemessen und benannt:** der Marker wird erreicht, **ohne dass sein Name als Wort
vorkommt** — `mv .claude .claude_off`, `rm .claude/HANDOVER*`, `rm -f .claude/*`,
`find .claude -name 'HANDOVER*' -delete`, oder ein per Substitution zusammengesetzter Pfad (je rc 0,
gepinnt). Das zu schließen hieße, das Dateisystem zu modellieren statt Wörter zu lesen.
**Einordnung:** als Angriff **niedrig** — im Piloten hat das Modell die Löschung von sich aus als
direkten Bypass verweigert; als **Dokumentationslücke mittel**, denn der Docstring versprach
„NAMED, unclosed gaps, each measured" und nannte genau diese Klasse nicht.

**Die Kehrseite derselben Regel ist eine Über-Verweigerung, und die ist gewollt (R3-4):** weil ein
unquotiertes Nicht-Lese-Verb mit dem Markerwort verweigert wird, trifft es auch eine Zeile, die den
Marker nur **sichert** oder **erwähnt** — `cp .claude/HANDOVER_PENDING /tmp/backup` und
`git commit -m "docs: explain HANDOVER_PENDING"` sind beide rc 2. Das ist die sichere Richtung: die
Allowlist verweigert im Zweifel, damit kein ungelisteter Entferner durchkommt, und der Preis ist
Reibung auf einer seltenen, gutartigen Zeile bis zum Neustart.

**Eine neue, benannte Über-Verweigerung ist der Preis der Terminator-Bedingung:** ein
Here-Document, dessen Delimiter-Zeile **nicht im selben Werkzeugaufruf** steht, bekommt seinen
Körper als Befehle vorgelegt. Gemessen gegen reales bash: `cat <<EOF⏎python … capture` führt bash
nicht aus, dieser Leser verweigert es (rc 2); ebenso `<<EOF` (unquotiert) mit `\` am Ende der
Körperzeile, wo bash über `EOF` hinaus schluckt. Beide sind mit
`test_handover_guard_over_refuses_an_unterminated_heredoc` festgenagelt, damit der Preis sichtbar
bleibt. Die umgekehrte Richtung wäre ein Loch, und genau das war sie.

**Urteil: Ausnahme, Abnahme offen** — die verbleibende Restklasse (Substitution, ungelisteter
Wrapper, gewrappte Shell, kodiert) ist **bewusst nicht** geschlossen. Sie zu schließen hieße zu
beantworten, was eine Zeichenkette später ausführen wird; das ist das Parser-Kaninchenloch, gegen
das DEC-0029 entschieden hat. Das Bedrohungsmodell (DEC-0032) ist ein **wohlmeinender**
Einstiegsagent, der weiterarbeitet, kein Gegner, der absichtlich verschleiert.

**Was stattdessen begrenzt:** die eigentliche Grenze ist der Neustart selbst — nach ihm sind die
Kit-Gates aktiv und `gate_write_scope`/`gate_dispatch` fangen dieselben Ableitungen strukturell.
Bis dahin ist der Guard ein Gurt, kein Sandkasten (Docstring). **Sozial** ergänzt: der Einstiegsagent
folgt seiner Verfassung, die ihm die Ableitung ohnehin untersagt.

**Rote Tests ohne den Fix.** `test_hooks.py::test_handover_guard_blocks_laundered_engine_calls` —
11 Fälle kamen gegen den Vor-Rework-Hook mit rc 0 statt 2 zurück (drei Fortsetzungen, acht
zusammengesetzte Kommandos); `test_handover_guard_allows_benign_multiline_reads_and_heredoc_bodies`
— 6 Fälle kamen mit rc 2 statt 0. Für Runde 3 ist **jede einzelne Mechanik** in einer Kopie
außerhalb des Repos zurückgebaut und gemessen worden, statt einer pauschalen Behauptung:
Terminator-Bedingung → `unterminated_heredoc`; Umleitungsgrenze →
`false_heredoc_arithmetic_shift_closed`; Kommentar-Abschnitt → `false_heredoc_in_a_comment_closed`;
Reihenfolge (Heredoc vor dem Zusammenziehen) → der Planweg-Fehlalarm
`…masterplan.md <<'EOF'⏎python … capture \⏎EOF⏎ls` (rc 0 gebaut, rc 2 mit der alten Reihenfolge);
zweite Namensposition → `case_pattern`, `function_body`; Lese-Position → `read_word_as_argument`,
`read_word_as_option_value`; Marker-Regel → alle **11** Fälle von
`test_handover_guard_refuses_removing_its_own_marker` (gegen den Klon ohne die Regel rc 0 statt 2),
mit `test_handover_guard_still_lets_the_marker_be_read` als Gegenprobe und
`test_handover_guard_marker_residue_is_named_not_closed` als Pin des Rests. Dazu misst
`test_every_separator_character_is_load_bearing` das andere
Ende der Trenner-Menge über den echten Einstiegspunkt `_handle_shell` (ein eingeschleustes `@` wird
als toter Eintrag gemeldet), und
`test_handover_guard_wrapped_engine_forms_are_the_named_residue` pinnt die Restklasse.
Für Runde 4 ebenso je Mechanik zurückgebaut: Leerzeilen-Ersatz statt Löschung →
`heredoc_redirect_line_continues`(+`_into_a_pipe`) rc 0 statt 2; quote-respektierende Tokenisierung
→ `help_flag_in_a_quoted_value`, `dash_h_in_a_quoted_value` rc 0 statt 2 und der Fehlalarm
`git commit -m "… (…) … python … capture"` rc 2 statt 0.

**Runde 5 (TSK-0054, BUG-0017) — die Approval-Frage-Verweigerung fängt nur den TREUEN Marker-Relay.**
Der Guard verweigert jetzt zusätzlich eine `AskUserQuestion`, deren `tool_input` den Approval-Marker
trägt (`_APR_REQUEST_MARKER = \[APR-REQ:`), damit die Einstiegssitzung den Scope-Approval-Weg nicht
STARTET (der Mint scheiterte dort und der Agent erfand daraus `/hooks` — EVD-0020,
`docs/reviews/2026-08-12-bug0017-live-confirm.md`). Der Marker ist **byte-genau** der des echten
Emitters (`team-kits/kernel/approvals.py` schreibt `[APR-REQ:<id>]`, `gate_approval.py` liest
`\[APR-REQ:<32 hex>\]`), also nicht inert. **Der Rest — dieselbe DEC-0029-Klasse:** gefangen wird nur
ein **byte-treuer, case-exakter** Relay. Eine Halluzination, die den Marker WEGLÄSST oder verstümmelt/
kleinschreibt, ist von einer normalen Frage nicht unterscheidbar und entkommt; die Alternative wäre,
Absicht aus Freitext zu modellieren (gegen die DEC-0029 entschied) und dabei die Einstiegs-Gate-Fragen
mitzuverweigern. Narrow by design; in der Guard-Docstring benannt.

**Live gemessen 2026-08-13** (`docs/reviews/2026-08-13-tsk0054-live-confirm.md`, Rohprotokolle in
`docs/reviews/2026-08-13-tsk0054-live-logs/`): EINE echte Einstiegssitzung reichte die Kernel-Frage
mit byte-treuem `[APR-REQ:<id>]` in `tool_input` durch, der Guard verweigerte sie (rc 2,
`apr-live2.jsonl` Sätze 10/11) — **eine** gemessene Weitergabe, keine Eigenschaft des Weiterreichens;
ob die EVD-0020-Frage der Einstiegssitzung den Marker trug, ist nirgends aufgezeichnet (Rohprotokoll
gelöscht — die frühere Fassung dieses Absatzes behauptete Deckung mit einem Zitat, das nur Phase 2
belegt; korrigiert). Die Verhaltensbestätigung ist im selben Lauf erbracht: der Einstiegsagent erfand
auf dem Fortsetzungspfad kein `/hooks` und keinen Ersatz, sondern bat um den Neustart — auch mit der
`restart_required`-Diagnose vor Augen (ein Modell, ein Lauf; modellabhängige Aussage). Präzisierung
aus dem Lauf: tragend war auf dem natürlichen Pfad die ältere BUG-0016-Shell-Regel
(`request-approval` rc 2); der Marker entsteht ausschließlich im stdout der CLI (die Pending-Datei
trägt ihn nicht, gemessen), der Ask-Zweig wurde darum in vier von fünf Sitzungen gar nicht erreicht.
Er ist der Riegel für Marker-Ankunft auf anderem Weg (Datei, Paste, ungelisteter Wrapper) — zweiter
Riegel, nicht erster.

**Rest desselben Laufs (F2): der `/hooks`-vorschlagende Diagnosepfad — das `hook_trust`-Feld ist
GESCHLOSSEN (TSK-0057/BUG-0036, 2026-08-14), die KLASSE nicht.** Der alte Pauschalsatz („the kit
update is in state %r — a changed bundle needs /hooks confirmation…", für JEDEN Nicht-aktiv-Zustand)
ist ersetzt: der Grund ist zustandsgenau (frische Installation → genau EIN neuer Sessionstart, und
NUR wenn der einlösende SessionStart-Hook wirklich registriert ist — sonst Scaffold-Rat statt
Endlosschleife; verändertes Bundle → die Spec-II.8-Formulierung, die dort korrekt ist), und
Record-Inhalt kann keine eigenen Wörter mehr in den Grund schmuggeln (Form-Eigenschaft: zitiert wird
nur, was wie Name/Hash geformt ist; alles andere wird beschrieben). Elf Tests rot ohne den Fix,
Prüfer-PASS mit 1008-Zeilen-Nachweis, dass das grüne Urteil unverändert blieb; Messtabelle in
`docs/reviews/2026-08-13-tsk0057-kit-state-measurements.md`. **Bewusst NICHT übernommen** wurde der
hier früher vorgeschlagene Wortlaut „restart — /hooks is not part of this flow": eine Verneinung
trägt den Token selbst hinein; der Neustart-Zweig nennt ihn gar nicht (derselbe Präzedenzfall wie
die Marker-Zeichenkette in `CLAUDE.md`).

**Was von der Klasse offen bleibt — „ein ausgelieferter Text reicht dem Einstiegsfenster einen
`/hooks`-Schritt", Träger gemessen 2026-08-14:** die Codex-Hinweiszeile in `environment_notes`
(`team-kits/kernel/report.py:2245-2248`; ob `/hooks` für die Codex-Fläche überhaupt der richtige
Schritt ist, ist UNGEMESSEN — auf Verdacht umschreiben hieße eine vielleicht wahre gegen eine sicher
ungemessene Aussage tauschen) und die Codex-Abschlusszeile des Scaffolds
(`team-kits/gen_provider_artifacts.py:1313`); dazu `report.py:2118` als der von Spec II.8
legitimierte Träger (verändertes Bundle). Nachbarreste derselben Runde: das `kit`-Feld aus
`kit_state.json` ist das letzte wörtliche Record-Echo der doctor-Fläche (O1,
`report.py:1974-1975`), und `kit_trust_state.py:23-27` behauptet einen fehlenden Ausgang, den
`transition()` hat — als **BUG-0037** erfasst. Beide mit Messung im Review-Dokument.

### L40 — Ein Subagent erreicht `set-preset`: die Subagenten-Regel kennt nur die Klasse „bestellt Arbeit" (TSK-0064)

**Mechanismus, als Eigenschaft:** Mit TSK-0064 (`BUG-0041`) hat der Kernel einen Befehl bekommen,
der die **Durchsetzungsschicht neu installiert** — `set-preset` schreibt `project.preset` und fährt
das Scaffold, das Rollen nach `.claude/agents` legt —, ohne Arbeit zu bestellen. Die
Subagenten-Regel von `gate_write_scope` (Regel 4) erkennt aber genau die Klasse „bestellt Arbeit":
`_ORDERING_COMMANDS` ist aus den CLI-Routen abgeleitet, die `create_task`/`create_lease` erreichen,
und `set-preset` erreicht keines von beiden. Die Ableitung ist damit **intakt und zu eng zugleich**
— eine neue Befehlsklasse (installiert Durchsetzung, bestellt nichts) liegt außerhalb ihrer
Definition.

**Kette (Prüfer der TSK-0064-Runde, 2026-08-15, echte Hook-Prozesse gegen die 8 registrierten
`Bash|PowerShell`-PreToolUse-Hooks eines gescaffoldeten Projekts, aus dessen eigener
`settings.json` gelesen):** als Subagent ist `python scripts/harness.py set-preset team` und
`… request-approval preset --preset …` bei **allen 8 Hooks** durchgelassen, während `create-task`
für denselben Subagenten rc 2 ist (Regel 4 arbeitet für ihre Klasse). Was ein Subagent damit
erreicht: eine vom Nutzer signierte, noch nicht angewandte Änderung zum **selbstgewählten
Zeitpunkt** auslösen (einschließlich des Entfernens von Peer-Rollen), und eine
**Upgrade**-Freigabe (leeres `removes`) innerhalb ihrer Stunde beliebig oft wiederholen —
gemessen: zweiter und dritter Lauf rc 0, je ein voller Scaffold-Lauf mit neuem
Backup-Verzeichnis, `kit_state: restart_required`, `.claude/HANDOVER_PENDING`. Was er NICHT
erreicht, ebenfalls gemessen: einen anderen **Inhalt** als den signierten — Freigabe A gegen
Preset B, Rollendrift zwischen Mint und Set, abgelaufene Freigabe sind alle verweigert (der Hash
deckt das Ergebnis).

**Begrenzung, und ihre eigene Grenze:** sobald `.claude/HANDOVER_PENDING` steht, verweigert der
**nutzerglobale** `handover_guard.py` weitere Läufe (rc 2 für beide Befehle, rc 0 für `doctor`).
Dieser Riegel ist aber kein Kit-Hook — ein Projekt ohne die globale Datei hat ihn nicht —, und er
trägt seine eigenen benannten Reste (L39: die Verbposition, die ein Wrapper besetzt; gemessen sind
einzelne Wrapper-Schreibweisen rc 0, eine Kommandoersetzung rc 2).

**Erweiterung (TSK-0067, gemessen 2026-08-16 vom Prüfer jener Runde):** dieselbe Klasse trifft
das **zweite** Kommando, das die Durchsetzungsschicht neu installiert — als Subagent
(`agent_id: sub-1`, `agent_type: backend-developer`) sind `python scripts/harness.py update-kit`
und `… request-approval kit_update` bei **allen 8** registrierten `Bash|PowerShell`-Gates rc 0,
während `create-task` für denselben Subagenten rc 2 bleibt. Ein Unterschied zur
`set-preset`-Hälfte, gemessen: die **Wiederholung trägt hier nicht** — der zweite Lauf ist rc 1
(„already runs the staged … kit"). Was der Subagent kontrolliert, ist also nur der
**Zeitpunkt**, einmalig. Daneben, als bewusster Nicht-Weg derselben Runde: ein
**Reparatur-Scaffold auf gleicher Version** (manipuliertes Bundle) hat weiterhin keine Route aus
der Sitzung — `update-kit` verweigert „already runs the staged release", und das ist gewollt:
ein Befehl, der ein Bundle neu segnet, wäre die Selbstfreigabe, die `write_kit_state.py`
verhindert; die Vertrauens-Remedy von `gate_dispatch` zeigt dort korrekt auf den Nutzer.

**Urteil: Rest mit gemessener Kette, kein Inhalts-Loch.** Die Autorisierung selbst ist die APR des
Nutzers und deckt das Ergebnis; was der Subagent kontrolliert, ist **Zeitpunkt und Wiederholung**
einer signierten Änderung, nicht ihr Inhalt (bei `update-kit` nur der Zeitpunkt, einmalig). Die
Reparaturstelle ist die Subagenten-Regel der
Kits: die abgeleitete Klasse um „installiert die Durchsetzungsschicht" erweitern (aus derselben
Quelle abgeleitet, aus der `set-preset` und `update-kit` ihre Wirkung beziehen) — eine
Kit-Runde, kein Repo-Gate.

### L41 — Was die Fehlermeldungen von `set-preset` nicht wissen: Skills und Provider-Artefakte im Abbruchfenster (TSK-0064)

**Mechanismus:** Nach einem abgebrochenen oder verweigerten Installationslauf liest der Kernel
zwei Dinge neu — das Besitzverzeichnis `.claude/team_kit_roles.txt` und die Rollendateien
`.claude/agents/<rolle>.md`, die es nennt (`kernel/presets._installed_state`). **Nicht** neu
gelesen werden `.claude/skills/<rolle>/`, die generierten Provider-Artefakte
(`.codex/agents/*.toml`, `.codex/hooks.json`, `.agents/skills/`) und Rollen-Artefakte, die diese
Installation nicht besitzt. Ein Abbruchfenster kann diese ungelesenen Teile in **beide**
Richtungen verfehlen: Artefakte fehlen, oder überzählige bleiben zurück.

**Kette (gemessen 2026-08-15, echtes Scaffold, Abbruch nach 1,5 s):** Prüfer der TSK-0064-Runde,
zweimal unabhängig — die Rollen waren zurück und beide Leser einig, während `.claude/skills` von
sieben Verzeichnissen auf **null** gefallen war; der Satz darüber lautete vor dem Fix „nothing is
missing". Umsetzer, Wiederholung derselben Frist — die Spiegelform: Besitzverzeichnis nennt fünf
Rollen, `.claude/agents` hält neun, `.claude/skills` sieben (Reste des halb installierten
Satzes). Beides räumt der **nächste vollständige Installerlauf** auf, er prunet nach demselben
Verzeichnis — kein dauerhafter Verlust.

**Urteil: Rest mit gemessener Kette, geschlossen ist die EHRLICHKEIT, nicht die Messung.** Seit
TSK-0064 tragen alle drei Ausgangs-Meldungen die Grenze im Klartext (`kernel/presets.UNREAD`, in
beiden Richtungen: fehlend *und* übrig) statt Vollständigkeit zu behaupten; der unbedingte Satz
ist von `test_the_outcome_messages_carry_the_limit_of_what_was_re_read` in beiden Fenstern rot
gedeckt. Wer die Skills wirklich prüfen will, lässt den Installer noch einmal laufen. Die
Schließrichtung — `_installed_state` liest auch Skill-Verzeichnisse und Provider-Artefakte —
ist eine Kit-Runde und lohnt erst, wenn das Fenster in der Praxis trifft (Pilot 4 beobachtet
den Preset-Fluss).

**Erweiterung (TSK-0067, gemessen 2026-08-16 vom Prüfer jener Runde):** dasselbe Fenster trifft
`update-kit`, mit einer Zuspitzung durch den dortigen F1-Fix (der „nichts bewegt"-Zweig setzt
bewusst **keinen** Stopp-Marker mehr, damit ein Konfigurationsfehler nicht die Sitzung tötet):
bei einem Abbruch nach 1,4 s von ~3,4 s waren **fünf Skill-Verzeichnisse weg**, während beide
Leser „unverändert" sagten — kein Marker, Sitzung lebt. Keine Datei der Durchsetzungsschicht
bewegte sich dabei (Bundle „recorded", `agents`/`settings.json` unverändert), der Regelsatz
unter einem laufenden Kind bliebe also der der Sitzung; die Meldung trägt die Grenze selbst
(`UNREAD` nennt „the role skills" ausdrücklich), und die Remedy **heilt gemessen**:
Wiederholungslauf rc 0, Skills 0 → 5, Marker gesetzt, Stempel bewegt. Der Richtungsentscheid
ist richtig — die Vorfassung stoppte die Sitzung über einen Baum, an dem nachweislich gar
nichts war, und das war die teurere Fehlrichtung; was bleibt, ist die ehrliche Restmenge.

### L42 — Drei gemessene Grenzen der Fortsetzungs-Mechanik (TSK-0065)

TSK-0065 (`BUG-0042`, `DEC-0044`) hat den Sitzungsabbruch zweiteilig beantwortet: verwaiste
Dispatches werden beim Sitzungsstart ehrlich gefegt (Definition: die anfordernde Sitzung ist
nicht die jetzt fragende), und ein Spezialisten-Zwischenstand (`staging/<TSK>/checkpoint.yaml`)
wird vom Nachfolger nur nach dreifacher Verifikation übernommen (Identität, Vertrag über den
`expected_outputs`-Digest samt Task-/Root-Revision, Artefakt-Bytes — seit der Nachbesserung mit
Pfad-Eingrenzung und „ohne Artefakt = abwesend"). Drei Grenzen bleiben, je gemessen in der
Prüfung 2026-08-16:

**(a) Kernel-seitig fällt die Waisen-Frage bei fehlender Sitzungs-Id nicht zu.**
`dispatch.orphaned_dispatches(state, None)` — und ebenso mit `""` — liefert **jeden**
aufgezeichneten Dispatch als verwaist (gemessen von Prüfer und Umsetzer unabhängig); was davor
steht, ist allein der Kit-Hook (`_kernel.py`, gibt bei fehlender/leerer Id `None` zurück und
fegt nichts — gemessen für fehlenden Schlüssel, Leerstring und Whitespace). Die Definition
gehört in den Kernel, nicht in den einen Aufrufer; ein zweiter Kernel-Aufrufer ohne diese
Vorsicht würde alles fegen. Nebenwirkung derselben Konstruktion, als Preis des ehrlichen
Fixes: ein Dispatch im Fenster zwischen `dispatch` und Antritt (Lease existiert, trägt aber
noch keine Sitzung) wird bei jedem Sitzungsstart als „LEFT ALONE / unentscheidbar" gemeldet —
melden statt zerstören ist die richtige Richtung, aber es ist wiederkehrendes Rauschen im
Briefing und gehört mit in die Folgerunde.

**(b) Was der Datensatz ÜBER die Dateien sagt, prüft niemand.** Ein handgeschriebener
Checkpoint mit **korrekten** Digests bleibt möglich — `staging/` ist genau das Verzeichnis, in
das ein dispatchter Spezialist schreiben darf. Die Verifikation misst Baum und Task neu; die
Prosa (`note`, `next_step`) ist unverifiziert, und die Verfassung sagt dem Nachfolger „Read it,
judge it". Benannt im Modul-Docstring und im Verdikt-Text; die Begrenzung ist, dass nur
signierte Fakten (Digests, Revisionen) die Übernahme öffnen, nie die Prosa.

**(c) Ungemessen bleiben zwei Betriebsfragen:** ob eine zweite **gleichzeitige** Sitzung im
selben Projekt vom Fegen getroffen würde (der Term beweist „woanders angefordert", nicht
„Anforderer ist tot"; Begrenzung: der Sweep landet nur auf Status, an denen ein Mensch
weiterhandelt, und zerstört keine noch auflösbare Bindung), und ob der Provider einer
weiterlaufenden Sitzung über Kompaktierung/Resume je eine **neue Id** gibt (sähe von innen wie
ein Sitzungsende aus). Beides steht als „NOT measured" im Code; die Id-Frage ist ein Kandidat
für die nächste echte Provider-Messrunde (`tools/provider_observations.json`).

**Urteil: Rest, keine offene Angriffskette in dieser Konstruktion.** (a) ist durch den einzigen
existierenden Aufrufer begrenzt und seine Schließrichtung (Kernel-seitiges fail-closed) eine
kleine Folgerunde; (b) öffnet keine Übernahme, weil nur Gemessenes sie öffnet; (c) ist ehrliche
Unwissenheit mit benannter Messrichtung, keine Behauptung.

### L43 — Was die neue PM-Shell-Regel (Regel 5) nicht erreicht: Werkzeugsprache, PowerShell-Cmdlets, unauflösbare Erweiterungen, Wrapper (TSK-0070)

**Anlass:** FR-0013 — `guard_pm_scope` der Kits deckte die Schreibwerkzeuge, nicht die Shell; ein
PM konnte `echo … > services/pay.py` an ihm vorbei fahren. TSK-0070 hat die Entscheidung
gemessen getroffen (Variante b, sauberer Schnitt: Dateieigenschaft bei `guard_pm_scope`,
Kommandozeilen-Zerlegung bei `gate_write_scope`, Regel 5 greift an der **einen** Schreibposition,
die die Shell-Syntax selbst definiert — dem Ziel einer bytehaltenden Umleitung) und die
Beschwichtigungsprosa des alten Docstrings („95%-Wächter; der QA-Gate ist der harte Riegel")
durch die Messung ersetzt: der QA-Riegel fragt nur nach einem **Verdikt**, und dasselbe Lead
erzeugt Verdikte selbst — er ist also über Autorschaft blind. Was Regel 5 **nicht** erreicht,
bleibt als benannte Restklasse, beidseitig getripwired in `ENFORCEMENT.md` aller drei Kits und
im Docstring von `_assert_the_lead_lands_no_code`:

- **Werkzeugsprachliche Writes** (`cp`, `mv`, `tee`, `sed -i`, `python -c`, `rm`): die Shell
  landet dort keine Bytes selbst, das Werkzeug schreibt aus seiner eigenen Sprache/Argumentliste.
  Die L4-Klasse — eine Verbliste wäre genau die Behauptung, die schon zweimal eine Datei zu kurz
  war; darum nicht aufgezählt, sondern als Grenze benannt.
- **PowerShell-Cmdlets** (`Out-File`, `Set-Content`, `Add-Content`, `Tee-Object`): dieselbe
  Klasse in der anderen Shell, gemessen rc 0, mit eigenem Test
  (`test_a_powershell_cmdlet_write_is_the_named_residue_too`).
- **Unauflösbare Erweiterungen** als Umleitungsziel (`$(cmd)`, Backticks, eine Variable, die die
  Zeile **nicht** zuweist): B2 löst nur die **Zeilen-eigenen** Zuweisungen auf; alles, was erst
  eine laufende Shell kennt, bleibt offen. `$UNSET/pay.py` verweigert übrigens (die Endung
  überlebt im Wort — sichere Über-Verweigerung), gehört also nicht hierher.
- **Wrapper** (`sh -c '…'`, `bash -c '…'`, `eval '…'`): schalten **alle** Kommandozeilenregeln ab,
  weil der innere Befehl dem Parser verborgen bleibt — gemessen läuft so auch `sh -c 'python
  scripts/harness.py create-task'` als Subagent durch (rc 0), also dieselbe **vorbestehende**
  Klassengrenze wie Regel 4 (die Subagenten-Regel), nicht neu von Regel 5. Verwandt mit der
  Interpreter-Klasse H11 und dem Handover-Wrapper L39.

**Über-Verweigerungen, alle in der billigen Richtung, gemessen und in den Batterien:** `~/pay.py`,
`$HOME/pay.py` (nicht platzierbar → nach Dateinamen beurteilt), `Docs/…` auf einem
case-insensitiven Host, ein Ziel unter `project_memory/staging/**` (fällt in Regel 1), `3>& …`
(schreibt in bash keine Datei, wird trotzdem verweigert). Reibung, kein Loch.

**Urteil: Rest, benannte Restklasse, keine der Über-Verweigerungen ist ein Loch.** Der
Datenverlust-Kern (die bytehaltenden Umleitungsformen `>`, `>>`, `>|`, `&>`, `>&`, und das
Variablenziel derselben Zeile) ist geschlossen und rot-getestet; was bleibt, ist Werkzeugsprache
und Wrapper, deren Schließung eine Verbliste oder einen Interpreter-Leser bräuchte (L4/H11) — das
ist eine eigene Abwägung Nutzen gegen Wartungslast, keine offene Naht dieser Runde. Der harte
Rückhalt gegen lead-geschriebenen Code bleibt gemessen `gate_pipeline` bei Merge/Push (urteilt
über Qualität, nicht Autorschaft) — so benannt, nicht als Autorschaftsriegel behauptet.

### L44 — Ein Zeichen, das die Shell nie sieht, und eine Fortsetzung, die sie nicht kennt — GESCHLOSSEN (TSK-0084)

**Mechanismus, zwei Hälften derselben Ursache:** ein Leser urteilt über einen Text, den die
*benannte* Shell so nie bekommt.

1. **Das Bash-Werkzeug löscht ein blankes CR**, bevor bash parst. Gemessen 2026-08-24, indem jede
   Shell eine Zeichenkette zurückschreibt und die **Bytes** verglichen werden, über jedes
   C0-Steuerzeichen, DEL, U+0085, U+2028 und U+2029: genau **ein** Zeichen der Klasse überlebt den
   Weg nicht, das CR auf der `Bash`-Schiene, und zwar auf beiden Wegen (`bash -c <zeile>` und die
   Zeile auf stdin). Ein Backslash davor schützt damit das Zeichen **hinter** dem CR, und zwei
   Wörter **verschweißen** zu einem Pfad.
2. **`_compat._CONTINUATION_RX` war die Vereinigung beider Fortsetzungszeichen** und trug keinen
   Werkzeugnamen, entfernte also unter `tool_name: PowerShell` einen Umbruch, den PowerShell
   honoriert. PowerShell setzt über einen **Backtick** fort, nicht über einen Backslash — gemessen
   an echten Prozessen.

**Gemessene Ketten — vorher offen, jetzt zu.** In echten, außerhalb des Repos aufgesetzten
Projekten, jeweils mit Dateizeugen:

| Zeile | tool | vorher | nachher |
|---|---|---|---|
| `echo poison > project_mem\<CR>ory/approvals/APR-0001.yaml` | Bash | Gate rc 0 → bash rc 0 → das kanonische Item enthält `poison` | **Gate rc 2**, Item unverändert |
| `Get-Content README.md \<LF>Set-Content -Path .claude/settings.json -Value POISONED` | PowerShell | Gate rc 0 → `powershell.exe` rc 0 → Datei überschrieben | **Gate rc 2**, Datei unverändert |
| dieselbe Zeile mit `\`+CRLF | PowerShell | Gate rc 0 → rc 0 → Datei überschrieben | **Gate rc 2** |

Die volle Familie — 9 Umbruch-Schreibweisen × 2 Werkzeuge × 2 Kits, 36 Zeilen — zeigt nachher
**kein** einziges `POISONED`: entweder rc 2, oder rc 0 mit einer Shell, die dann nachweislich nichts
schreibt (bash führt `echo hello tee .claude/settings.json` als **einen** Befehl aus, PowerShell
antwortet auf `Get-Content README.md `<LF>Set-Content …` mit rc 1).

**Wie geschlossen.**

- Hälfte 1 als **Verweigerung**, nicht als Reparatur: `_kernel._EATEN_IN_FLIGHT` nennt pro Werkzeug
  die Zeichen, die dessen Transport löscht, und `_kernel.payload` — die eine Tür, durch die jedes
  blockierende Gate geht — verweigert eine Zeile, die eines davon trägt, mit dem Grund und einer
  Abhilfe für den Nutzer. Reparieren ginge nicht: das CR löschen hätte bash' Lesart und PowerShells
  verloren, und eine Verschweißung überquert eine Wortgrenze, wäre also eine zweite
  **Tokenisierung** der ganzen Zeile.
- Hälfte 2 als **werkzeugabhängige Fortsetzung**: `_compat._CONTINUATION_BY_TOOL` (`Bash` →
  Backslash + Umbruch, `PowerShell` → Backtick + LF), voreingestellt aus dem Werkzeugnamen der
  Nutzlast, die dieser Prozess gelesen hat (`_compat.gated_shell`) — dieselbe Antwort auf
  „nicht durch neun Aufrufstellen fädeln“, die `_LAST_PAYLOAD` für die Befehlszeile schon gibt.

**Kosten der Verweigerung, gemessen:** über alle 22 Test-Module und alle Hook-Dateien der drei Kits
(111 Dateien, geparst) trägt **keine** legitime Befehlszeile ein blankes CR. Die acht, die eines
tragen, sind ausnahmslos Angriffsformen, die ohnehin rc 2 erwarten; die übrigen Treffer sind
Zeichenklassen im Code. Ein **CRLF** wird ausdrücklich **nicht** verweigert — sein CR fällt weg und
der LF dahinter bleibt der Umbruch, den er war —, und dasselbe blanke CR auf der
**PowerShell**-Schiene ebenfalls nicht, weil PowerShell es wirklich bekommt.

**Urteil: geschlossen, in der sicheren Richtung, mit Rot-Beweis.** Laufende Behauptungen:
`tools/test_hooks_v2.py::test_a_line_carrying_a_character_its_shell_never_sees_is_refused` und
`tools/test_hooks_v2.py::test_a_continuation_the_named_shell_does_not_honour_is_not_joined`.

**Was bleibt, benannt.** Die `PreToolUse`-Gates **dieses** Repos (`.claude/hooks/`) erben die
werkzeugabhängige Fortsetzung, weil `_harness` die Nutzlast durch dasselbe `_compat` liest — die
CR-**Verweigerung** aber nicht, denn die sitzt in `_kernel.payload`, und `_harness` ruft
`_compat.load` direkt. `.claude/**` ist verbotener Bereich für den Umsetzer; gemessen wird das vom
Prüfer read-only.

## 12. Loecherliste der Repo-Gates -- GENERIERTER ZEIGERINDEX

<!-- GENERATED by tools/migrate_holes.py -- do not edit by hand. The holes are ITEMS; this is a pointer index regenerated from them, and a hand edit is what test_the_hole_index_in_the_document_is_the_one_the_items_generate reports. -->

Jedes Loch ist ein Item (`BUG` mit `hole_number`) und wird dort gelesen. Wo die Nummer verlinkt ist, liegt unter `docs/holes/` zusaetzlich der Volltext, den die Migration aus dem frueheren Dokument uebernommen hat; ein spaeter erfasstes Loch hat keinen und ist deshalb nicht verlinkt. Neue Nummern vergibt der Kernel (`capture --hole`), nicht die Hand.

| Loch | Item | Stand | Titel |
|---|---|---|---|
| [H1](docs/holes/H1.md) | BUG-0093 | VERIFIED | Der Digest beschreibt den Baum vor der Zeile, nicht den, den der Commit aufzeichnet — GESCHLOSSEN |
| [H2](docs/holes/H2.md) | BUG-0094 | VERIFIED | Nur das Literal `commit` — GESCHLOSSEN (TSK-0056, BUG-0034), mit benannten Resten |
| [H3](docs/holes/H3.md) | BUG-0095 | VERIFIED | `project_memory/` war für Werkzeuge offen — GESCHLOSSEN, mit einer benannten Resthälfte |
| [H4](docs/holes/H4.md) | BUG-0096 | VERIFIED | Ein Pfad hat mehr als einen Namen — GESCHLOSSEN, in zwei Stufen |
| [H5](docs/holes/H5.md) | BUG-0097 | VERIFIED | `settings.local.json` war ungeschützt — GESCHLOSSEN |
| [H6](docs/holes/H6.md) | BUG-0098 | VERIFIED | Eine Nutzlast, die ein Gate nicht lesen kann, war ein Ja — GESCHLOSSEN, Erreichbarkeit ungemessen |
| [H7](docs/holes/H7.md) | BUG-0099 | ACCEPTED_EXCEPTION | `carries_work` verlangt keinen erreichbaren Endzustand — OFFEN |
| [H8](docs/holes/H8.md) | BUG-0100 | VERIFIED | Acht Tests hingen am Status *eines* Items — GESCHLOSSEN |
| [H9](docs/holes/H9.md) | BUG-0101 | REJECTED | Inhalt in diesem Auftrag nicht enthalten |
| [H10](docs/holes/H10.md) | BUG-0102 | ACCEPTED_EXCEPTION | Codehälften ohne rote Mutation — ZWEI GESCHLOSSEN, keine erschöpfende Suche |
| [H11](docs/holes/H11.md) | BUG-0103 | ACCEPTED_EXCEPTION | Ein Interpreter führt Code aus, den kein Gate lesen kann (neu, Preis des Fixes zu F2) |
| [H12](docs/holes/H12.md) | BUG-0104 | ACCEPTED_EXCEPTION | Ein Subagent kann sich die Ausnahme von Gate 2 selbst ausstellen |
| [H13](docs/holes/H13.md) | BUG-0105 | TRIAGED | Der Produzent ist als DATEI geschützt, nicht als Verzeichnis |
| [H14](docs/holes/H14.md) | BUG-0106 | ACCEPTED_EXCEPTION | Gate 3 druckt den Befehl, der es aufhebt |
| [H15](docs/holes/H15.md) | BUG-0107 | VERIFIED | Gate 1 hängt jetzt an privaten Helfern eines Kit-Hooks (neu, Preis desselben Fixes) |
| [H16](docs/holes/H16.md) | BUG-0108 | ACCEPTED_EXCEPTION | Der Pfad steht in einer Variablen, das Gate liest den Text (neu, TSK-0008) |
| [H17](docs/holes/H17.md) | BUG-0109 | VERIFIED | Die andere Schreibweise einer Funktionsdefinition — GESCHLOSSEN (TSK-0011) |
| [H18](docs/holes/H18.md) | BUG-0110 | TRIAGED | Das Repo als Operand eines Kopier- oder Archivbefehls gilt als Schreibzugriff (TSK-0008, korrigiert TSK-0011) |
| [H19](docs/holes/H19.md) | BUG-0111 | TRIAGED | Ein Kandidat, der einen VORFAHREN eines geschützten Baums nennt (neu, TSK-0011) |
| [H20](docs/holes/H20.md) | BUG-0112 | VERIFIED | Wo das Gate einer Bewegung nicht folgen kann, bleibt es stehen (neu, TSK-0011) |
| [H21](docs/holes/H21.md) | BUG-0113 | ACCEPTED_EXCEPTION | `Push-Location`/`Pop-Location` fehlen im Verzeichnis-Vokabular (neu, TSK-0011) |
| [H22](docs/holes/H22.md) | BUG-0114 | ACCEPTED_EXCEPTION | Die Read-only-Klassifikation gilt pro Stufe, der Pfad reist weiter (neu, TSK-0011) |
| [H23](docs/holes/H23.md) | BUG-0115 | TRIAGED | Ein unerreichbarer Pfad kostet die Beurteilung, nicht mehr die Frist (neu, TSK-0011) |
| [H24](docs/holes/H24.md) | BUG-0116 | VERIFIED | Ein Verzeichnisverb, das der Leser nicht als Verb der Zeile sieht (neu, TSK-0013) |
| [H25](docs/holes/H25.md) | BUG-0117 | ACCEPTED_EXCEPTION | Die Frist, die ein Gate sich zugesteht, und die, nach der es getötet wird (neu, TSK-0013) |
| [H26](docs/holes/H26.md) | BUG-0118 | VERIFIED | Ein Trenner, den der Leser nicht als Trenner las — GESCHLOSSEN (TSK-0013, erweitert TSK-0015) |
| [H27](docs/holes/H27.md) | BUG-0119 | VERIFIED | Die Kindschaft eines Verzeichnisverbs hatte eine Schreibweise — GESCHLOSSEN (TSK-0013, duale Hälfte TSK-0098) |
| [H28](docs/holes/H28.md) | BUG-0120 | VERIFIED | Ein Verzeichnis, das existiert und nicht betretbar ist — GESCHLOSSEN (TSK-0013, korrigiert TSK-0015) |
| [H29](docs/holes/H29.md) | BUG-0121 | VERIFIED | Eine Operandenliste, die dieser Leser nicht verbuchen kann (neu, TSK-0015) |
| [H30](docs/holes/H30.md) | BUG-0122 | VERIFIED | Ein Wort, das die Shell nicht als dieses Verb ausführt, und ein Pop ohne sichere Richtung (neu, TSK-0017) |
| [H31](docs/holes/H31.md) | BUG-0123 | VERIFIED | Eine Erweiterung, die die Quotierung unterdrückt (neu, TSK-0019) |
| [H32](docs/holes/H32.md) | BUG-0124 | ACCEPTED_EXCEPTION | Ein Befehl, den eine Ersetzung einführt (neu, TSK-0019) |
| [H33](docs/holes/H33.md) | BUG-0125 | VERIFIED | Die erweiternde Antwort kam von einer Funktion, die eine andere Frage beantwortet (neu, TSK-0021) |
| [H34](docs/holes/H34.md) | BUG-0126 | VERIFIED | Die Prosa-Entfernung löscht eine quotierte Spanne hinter einer Flagschreibweise, unabhängig vom Verb (neu, TSK-0021) |
| [H35](docs/holes/H35.md) | BUG-0127 | VERIFIED | Was das Lesen einer Zeile kostet, war durch keine Frist begrenzt (neu, TSK-0021) |
| [H36](docs/holes/H36.md) | BUG-0128 | ACCEPTED_EXCEPTION | Ein einzelner Aufruf nach C gibt den Interpreter nicht zurück (neu, TSK-0021) |
| [H37](docs/holes/H37.md) | BUG-0129 | VERIFIED | Die Messvorrichtung selbst schreibt den Baum, den sie misst (neu, TSK-0022) |
| [H38](docs/holes/H38.md) | BUG-0130 | ACCEPTED_EXCEPTION | Ein Programm, das ein Hier-Dokument einer Shell übergibt, liest keines der Gates (neu, TSK-0022) |
| [H39](docs/holes/H39.md) | BUG-0131 | ACCEPTED_EXCEPTION | Endzustände, die dieses Repo nicht ehrlich erreichen kann: TSK `DONE`, BUG `VERIFIED` (neu, TSK-0055) |
| [H40](docs/holes/H40.md) | BUG-0132 | ACCEPTED_EXCEPTION | Vertragszitationen außerhalb der `.py`-Quellen von `.claude/hooks/` liest kein Stolperdraht (neu, TSK-0058) |
| [H41](docs/holes/H41.md) | BUG-0133 | VERIFIED | Vier gemessene Grenzen des Zeiger-Wächters (neu, TSK-0009) |
| [H42](docs/holes/H42.md) | BUG-0134 | VERIFIED | `INV.scope` als Liste geschrieben schaltete die Testabdeckungs-Regel still ab — GESCHLOSSEN (TSK-0060) |
| [H43](docs/holes/H43.md) | BUG-0135 | VERIFIED | Was der Kernel selbst schreibt, lag außerhalb der Feldmenge, die der Sweep abgeleitet hat — GESCHLOSSEN (TSK-0059) |
| [H44](docs/holes/H44.md) | BUG-0136 | ACCEPTED_EXCEPTION | Vier gemessene Grenzen der Amendment-Ableitung (neu, TSK-0062) |
| [H45](docs/holes/H45.md) | BUG-0137 | VERIFIED | Zwei Grenzen der Arbiter-Härtung der Gate-Suite (neu, TSK-0063) |
| [H46](docs/holes/H46.md) | BUG-0138 | VERIFIED | `>&datei` ist eine bytehaltende Umleitung, die Gate 1 nicht als Schreibzugriff sah — GESCHLOSSEN (TSK-0070, über die Kit-Leih-Mechanik mitgeheilt) |
| [H47](docs/holes/H47.md) | BUG-0139 | TRIAGED | Das Repo-Gate leiht den Ziel-Leser des Kits, aber nicht dessen Zeilen-Zuweisungskarte: `F=…; > $F` schreibt kanonischen Zustand an Gate 1 vorbei — OFFEN (neu, TSK-0070) |
| [H48](docs/holes/H48.md) | BUG-0140 | VERIFIED | Ein offener Lesehandle friert das Board für die Dauer der Sitzung ein; das einzige aktive Signal ist eine im Hook-Pfad praktisch ungelesene stderr-Zeile — OFFEN als bewusster Tausch (neu, TSK-0071) |
| [H49](docs/holes/H49.md) | BUG-0141 | ACCEPTED_EXCEPTION | Die zweite Vertragsverletzung eines Subagenten läuft ungebremst durch (neu, TSK-0075) |
| [H50](docs/holes/H50.md) | BUG-0142 | ACCEPTED_EXCEPTION | Ein gebundenes Kind ohne `SubagentStop` ist nach dem TTL-Sweep unsichtbar — OFFEN als bewusster Tausch (neu, TSK-0080) |
| [H51](docs/holes/H51.md) | BUG-0143 | ACCEPTED_EXCEPTION | Nach der einen Verweigerung schweigt der Melder für denselben Befund — offen (neu, TSK-0080) |
| [H52](docs/holes/H52.md) | BUG-0144 | VERIFIED | Ein Zombie-Dispatch hält rollengleiche id-lose Zuordnungen dauerhaft still — offen (neu, TSK-0080) |
| [H53](docs/holes/H53.md) | BUG-0145 | ACCEPTED_EXCEPTION | Die Lebensdauer von `stop_hook_active` ist ungemessen — offen (neu, TSK-0080) |
| [H54](docs/holes/H54.md) | BUG-0146 | ACCEPTED_EXCEPTION | Ein ungebunden laufendes Kind wird als „nie verfolgt" gemeldet — offen, nicht blockierend (neu, TSK-0080) |
| [H55](docs/holes/H55.md) | BUG-0147 | ACCEPTED_EXCEPTION | Die Alt-Bestand-Brücke läuft ohne gemintete Freigabe, und ein Subagent erreicht sie — offen (neu, TSK-0081) |
| [H56](docs/holes/H56.md) | BUG-0148 | ACCEPTED_EXCEPTION | Ein abgebrochener Brückenlauf lässt ein gemischtes Bündel stehen — offen, erholbar (neu, TSK-0081) |
| [H57](docs/holes/H57.md) | BUG-0149 | VERIFIED | Ein Interpreter-Heredoc ist vor `gate_ledger_valid` unsichtbar (neu, Preis des TSK-0081-Fixes) |
| [H58](docs/holes/H58.md) | BUG-0150 | VERIFIED | `TSK DONE → VALIDATED` fordert keine Evidence — offen als Semantik-Entscheidung (neu, TSK-0082) |
| [H59](docs/holes/H59.md) | BUG-0151 | TRIAGED | Nichts treibt ein Projekt in die Phasen 6–9 — offen, die Leere ist jetzt gesagt (neu, TSK-0082) |
| [H60](docs/holes/H60.md) | BUG-0152 | VERIFIED | `document_sources` erzwingt nichts — offen, doppelt begrenzt (neu, TSK-0082) |
| [H61](docs/holes/H61.md) | BUG-0153 | TRIAGED | Kein Kit-Hook merkt, dass sein Fenster abläuft — offen, Schließrichtung gebaut (neu, TSK-0082) |
| [H62](docs/holes/H62.md) | BUG-0154 | VERIFIED | Die Köder-Prüfung des Ledger-Gates urteilt segmentweit — offen, Kandidat gemessen und zurückgestellt (neu, TSK-0083) |
| [H63](docs/holes/H63.md) | BUG-0155 | VERIFIED | Das Ledger-Gate verweigert seine eigene beworbene Remedy — GESCHLOSSEN (TSK-0083, `BUG-0064`) |
| [H64](docs/holes/H64.md) | BUG-0156 | VERIFIED | Jedes `>` eines Segments ist dem Ledger-Gate eine Umleitung, auch quotierte Prosa — offen, Über-Verweigerung als bewusster Preis (neu, TSK-0083) |
| [H65](docs/holes/H65.md) | BUG-0157 | ACCEPTED_EXCEPTION | Ein Wort, das die Shell erst durch Expansion herstellt, sieht dieser Leser nicht — offen, Loch, vorbestehend (benannt TSK-0083) |
| [H66](docs/holes/H66.md) | BUG-0158 | VERIFIED | `shell_readings` sagt „jede Lesart" zu und liefert nur die POSIX-Lesart — offen, Loch, vorbestehend (benannt TSK-0083) |
| [H67](docs/holes/H67.md) | BUG-0159 | VERIFIED | Köder und Geschwister werden nur befragt, wenn dieselbe Zeile schon blockiert — offen, Loch, vorbestehend (benannt TSK-0083) |
| [H68](docs/holes/H68.md) | BUG-0160 | VERIFIED | Zwei Schreibweisen, die verweigert werden, ohne zu schreiben — offen, Über-Verweigerung, naheliegender Fix gemessen falsch (TSK-0083) |
| [H69](docs/holes/H69.md) | BUG-0161 | TRIAGED | Die Gates dieses Repos erben die halbe CR-Härtung der Kits — offen, Werkbank, `DEC-0022` (TSK-0084) |
| [H70](docs/holes/H70.md) | BUG-0162 | VERIFIED | Der Vollständigkeits-Draht des Ledger-Gates fragt nach MUSTERN, also sieht er eine Ausnahme ohne Muster nicht — offen, Messlücke des Instruments (TSK-0083/TSK-0084) |
| [H71](docs/holes/H71.md) | BUG-0163 | VERIFIED | Was der Leser der Merge-Rückstandsliste NICHT entscheiden kann — offen, vier gemessene Grenzen (TSK-0086) |
| [H72](docs/holes/H72.md) | BUG-0164 | ACCEPTED_EXCEPTION | Was die Vier-Augen-Wand NICHT bindet — offen, gemessene Grenzen der Zweitlesungs-Mechanik (TSK-0087) |
| [H73](docs/holes/H73.md) | BUG-0165 | VERIFIED | Was die Entscheidungs-zuerst-Runde NICHT misst — offen, drei gemessene Grenzen (TSK-0089) |
| [H74](docs/holes/H74.md) | BUG-0166 | ACCEPTED_EXCEPTION | Was die schnellere Gate-Suite NICHT schützt — offen, gemessene Grenzen (TSK-0090) |
| [H75](docs/holes/H75.md) | BUG-0167 | VERIFIED | Was der E-Rechnungs-Leser NICHT prüft — offen, gemessene Grenzen des Geldpfads (TSK-0091) |
| [H76](docs/holes/H76.md) | BUG-0168 | ACCEPTED_EXCEPTION | Was der neue Dokument-Schreibweg NICHT bindet — offen, gemessene Grenzen (TSK-0092) |
| [H77](docs/holes/H77.md) | BUG-0169 | VERIFIED | Was die Wertsprache-Regel NICHT hält — offen, gemessene Grenzen (TSK-0093) |
| [H78](docs/holes/H78.md) | BUG-0170 | ACCEPTED_EXCEPTION | Ein Startmodus, der die Projekteinstellungen nicht lädt, entfernt den ganzen Durchsetzungsapparat — offen, von innen nicht schließbar (TSK-0094) |
| [H79](docs/holes/H79.md) | BUG-0171 | ACCEPTED_EXCEPTION | Was die Besitz-Ableitung der Dokument-Schreibroute NICHT bindet — offen, gemessene Grenzen (TSK-0096) |
| [H80](docs/holes/H80.md) | BUG-0172 | VERIFIED | Der Freigabe-Haken ließ sich in dieser Werkstatt von Hand fahren — GESCHLOSSEN (TSK-0098), mit benannten Resten |
| [H81](docs/holes/H81.md) | BUG-0173 | VERIFIED | Der Mint-Leser irrt in BEIDE Richtungen: eine unzerlegbare Zeile warnt zu viel, eine fehlende Datei zu wenig (neu, TSK-0097) |
| [H82](docs/holes/H82.md) | BUG-0174 | ACCEPTED_EXCEPTION | Was die interne Sicht-Schleife für Design-Entwürfe NICHT bindet — offen, gemessene Grenzen (TSK-0099) |
| [H83](docs/holes/H83.md) | BUG-0175 | VERIFIED | Ein Referenz-Skill erreichte nur Projekte auf dem Preset `all` — GESCHLOSSEN (TSK-0104), beide Ketten, mit benanntem Rest |
| [H84](docs/holes/H84.md) | BUG-0176 | ACCEPTED_EXCEPTION | Was die Ableitung der Referenz-Skills NICHT bindet — offen, gemessene Grenzen (TSK-0100) |
| [H85](docs/holes/H85.md) | BUG-0177 | ACCEPTED_EXCEPTION | Was die Herkunfts- und Bündelprüfungen NICHT sehen — offen, gemessene Grenzen (TSK-0100) |
| [H86](docs/holes/H86.md) | BUG-0178 | ACCEPTED_EXCEPTION | Was die Bestandsklassifikation NICHT sieht — offen, gemessene Grenzen (TSK-0101) |
| [H87](docs/holes/H87.md) | BUG-0179 | VERIFIED | Pin und Rollback hatten keinen Kernel-Befehl, und der Pin schwieg in der Sitzungsmeldung — GESCHLOSSEN (TSK-0104), mit benanntem Rest |
| [H88](docs/holes/H88.md) | BUG-0180 | VERIFIED | Der Rollback ist byte-gleich nur über die aufgezeichnete Menge, und ältere Sicherungen tragen keine — offen, gemessen (TSK-0101) |
| [H89](docs/holes/H89.md) | BUG-0181 | ACCEPTED_EXCEPTION | Ohne `git` kann die Vier-Augen-Buchung alte von neuen Zeilen nicht unterscheiden und tritt zurück (neu, TSK-0102, FR-0065) |
| [H90](docs/holes/H90.md) | BUG-0182 | VERIFIED | Zwei identische Buchungen EINES Belegs teilen sich ein Lesepaar (neu, TSK-0102, FR-0065) |
| [H91](docs/holes/H91.md) | BUG-0183 | VERIFIED | Der gerenderte Aktenplan-Baum zeigt den PLAN, nicht die Platte (neu, TSK-0102, FR-0031) |
| [H92](docs/holes/H92.md) | BUG-0184 | VERIFIED | Der Wurzel-Leser des Kernels löste EINEN Sprung auf, die Forschungskette ist zwei tief — GESCHLOSSEN (TSK-0106) |
| [H93](docs/holes/H93.md) | BUG-0185 | VERIFIED | Die Freigabe, auf die der genannte Ausweg zwang, gibt es laut Kernel und Verfassung nicht, sie unterschrieb keinen Inhalt und sie starb nie — GESCHLOSSEN (TSK-0106) |
| [H94](docs/holes/H94.md) | BUG-0186 | VERIFIED | Der gerenderte Forschungsbericht hatte keinen Schreibweg, während der Merge auf ihm bestand — Weg gebaut (TSK-0106), Verfassungszeile offen |
| [H95](docs/holes/H95.md) | BUG-0187 | VERIFIED | Die Ursprungsprüfung des Dispatchs fiel bei MEHRDEUTIGER Elternschaft offen aus, in allen Kits — GESCHLOSSEN (TSK-0106) |
| [H99](docs/holes/H99.md) | BUG-0188 | ACCEPTED_EXCEPTION | H11 hebt die Vier-Augen-Buchung mit auf: ein Skript trägt eine ungelesene Zeile nach `HEAD` und prägt die zweite Lesung (neu, TSK-0102, FR-0065) |
| [H105](docs/holes/H105.md) | BUG-0189 | VERIFIED | Das Rollengedächtnis des Bookkeepers war ein Kanal zwischen erster und zweiter Lesung, den `gate_second_booking` nicht sieht — GESCHLOSSEN (TSK-0105, FR-0064), mit benanntem Rest |
| [H106](docs/holes/H106.md) | BUG-0190 | VERIFIED | Der Umfang eines QS-Laufs ist Prosa: kein Feld und kein Hook zählt, ob die Suite einmal oder zehnmal lief (neu, TSK-0105, FR-0057) |
| [H107](docs/holes/H107.md) | BUG-0191 | ACCEPTED_EXCEPTION | Der Design-Brief trennt das ZIEL von der SCHREIBWEISE nur als Prosa: eine Prozessregel im Brief fängt nichts (neu, TSK-0105, FR-0069) |
| [H108](docs/holes/H108.md) | BUG-0192 | VERIFIED | Eine Evidenz, die ihren Laufumfang GAR NICHT erklärt, zählt weiter als Volllauf (neu, TSK-0106, FR-0040) |
| [H109](docs/holes/H109.md) | BUG-0193 | VERIFIED | „Sammelbar" ist geparst und nicht gefahren: ein übersprungener Test gilt als vorhanden (neu, TSK-0106, FR-0039) |
| [H110](docs/holes/H110.md) | BUG-0194 | ACCEPTED_EXCEPTION | Einen Check, den der Kernel nicht lesen kann, beantwortet er mit UNENTSCHIEDEN (neu, TSK-0106, FR-0039) |
| [H111](docs/holes/H111.md) | BUG-0195 | VERIFIED | Die Freigabe, auf der die Auditor-Routine reitet, hat in keinem Kit einen Erzeuger (neu, TSK-0107, FR-0038) |
| [H112](docs/holes/H112.md) | BUG-0196 | VERIFIED | Der Laufdatensatz der Routine ist ein Nebenprodukt und sagt nicht, was er zu sagen scheint (neu, TSK-0107, FR-0038) |
| [H113](docs/holes/H113.md) | BUG-0197 | TRIAGED | Das Fristenregister kennt kein „erledigt" (neu, TSK-0107, FR-0034) |
| [H114](docs/holes/H114.md) | BUG-0198 | ACCEPTED_EXCEPTION | Nach `/cd` läuft die Registrierung des ZIELVERZEICHNISSES, aber die Hook-DATEIEN des Startverzeichnisses (neu, TSK-0108, FR-0059) |
| [H115](docs/holes/H115.md) | BUG-0199 | ACCEPTED_EXCEPTION | `/cd` bringt die Subagenten und die `agent:`-Bindung des Ziels NICHT mit, obwohl der Changelog „agents" nennt (neu, TSK-0108, FR-0059) |
| [H116](docs/holes/H116.md) | BUG-0200 | ACCEPTED_EXCEPTION | Die Hook-REGISTRIERUNG wird mitten in der Sitzung neu gelesen — auch zwischen zwei Werkzeugaufrufen einer Runde (neu, TSK-0108, FR-0059) |
| [H117](docs/holes/H117.md) | BUG-0201 | VERIFIED | Nichts startet den Generator: eine Buchung bewegt die Seite nicht (neu, TSK-0109, FR-0032) |
| [H118](docs/holes/H118.md) | BUG-0202 | VERIFIED | Das Alter offener Posten und jeder Mahnstempel entstehen erst im Browser (neu, TSK-0109, FR-0032) |
| [H119](docs/holes/H119.md) | BUG-0203 | ACCEPTED_EXCEPTION | Keine Herkunft, und dem Ledger-Gate ist der Generator kein Bericht (neu, TSK-0109, FR-0032) |
| [H120](docs/holes/H120.md) | BUG-0204 | REJECTED | Die Haken-Spiegelregel hat keine Präsenz-Hälfte; für die Haken entscheidet die Registrierung, und das halten zwei Nachbartests (neu, TSK-0111) |
| [H121](docs/holes/H121.md) | BUG-0205 | VERIFIED | Der Leser der Löcherliste kennt keinen Code-Zaun; jedes Zitat hinter einem Zaun ist ungeprüft (neu, TSK-0111) |
| [H122](docs/holes/H122.md) | BUG-0206 | ACCEPTED_EXCEPTION | Der Melder über ungelesene Prosa fragt, was git TRÄGT, und nicht, was auf der Platte liegt (neu, TSK-0110, FR-0036) |
| [H123](docs/holes/H123.md) | BUG-0207 | VERIFIED | Eine Löschung mit einer FLAGGE kommt am Archiv-Wächter vorbei — seit TSK-0116 nur noch, wenn sie im ZIEL löscht (TSK-0113, FR-0050) |
| [H124](docs/holes/H124.md) | BUG-0208 | VERIFIED | Die Fristenmeldung liest eine Uhr, die keinem Feld dieses Kits gehört (neu, TSK-0113, FR-0034) |
| [H125](docs/holes/H125.md) | BUG-0209 | VERIFIED | Die Lösch-Regel des Archiv-Wächters war eine Verbliste, und jedes Verb daneben ging durch — GESCHLOSSEN (TSK-0114 gemessen, TSK-0116 behoben) |
| [H126](docs/holes/H126.md) | BUG-0210 | VERIFIED | Die Ablaufregel für eine offene Anfrage steht dreimal, und die drei Leser stehen auf zwei Uhren (neu, TSK-0115, FR-0075) |
| [H127](docs/holes/H127.md) | BUG-0211 | VERIFIED | Eine Handänderung an einem erzeugten Diagramm sieht zwischen zwei Zustandsschreibvorgängen niemand (neu, TSK-0115, FR-0080) |
| [H129](docs/holes/H129.md) | BUG-0212 | ACCEPTED_EXCEPTION | Was eine Zerstörung ist, bleibt eine Vokabelliste (neu, TSK-0116, FR-0050) |
| [H130](docs/holes/H130.md) | BUG-0213 | VERIFIED | Die leere Aufbewahrung ist über `add-filing-rule` nicht erreichbar (neu, TSK-0116, FR-0049) |
| [H131](docs/holes/H131.md) | BUG-0214 | ACCEPTED_EXCEPTION | Die Zeilennummern der Anlage EÜR stammen nicht aus dem amtlichen Vordruck (neu, TSK-0116, FR-0076) |
| [H132](docs/holes/H132.md) | BUG-0215 | ACCEPTED_EXCEPTION | Eine Antwort autorisiert jetzt N Ziele statt eines (neu, TSK-0117, FR-0074) |
| [H133](docs/holes/H133.md) | BUG-0216 | ACCEPTED_EXCEPTION | Der SDK-Weg prägt ohne die dritte Bedingung, und jedes Programm, das die Brücke ruft, prägt (neu, TSK-0117, FR-0083) |
| [H134](docs/holes/H134.md) | BUG-0217 | ACCEPTED_EXCEPTION | `blocked` ist ein Zustand, keine Messung (neu, TSK-0117, FR-0082) |
| [H135](docs/holes/H135.md) | BUG-0218 | VERIFIED | Der Zeugen-Halbteil der Überlappungsprüfung ist eine Stichprobe, keine Sprache (neu, TSK-0118, FR-0021) |
| [H136](docs/holes/H136.md) | BUG-0219 | VERIFIED | Die Vor-Dispatch-Prüfung hat in einem Kit-Projekt keinen ausführbaren Weg (neu, TSK-0118, FR-0021) |
| [H137](docs/holes/H137.md) | BUG-0220 | VERIFIED | Ein Haken-Docstring nennt einen Takt, den keine Verfassung mehr nennt (neu, TSK-0118, N2) |
| [H138](docs/holes/H138.md) | BUG-0221 | ACCEPTED_EXCEPTION | Die Konformitätsbefunde des Renderers verweigern nichts: der Datensatz beantwortet eine andere Frage (neu, TSK-0119, FR-0077/FR-0078) |
| [H139](docs/holes/H139.md) | BUG-0222 | VERIFIED | Die BUILD-Hälfte der Standard-Härtung ist nicht gebaut, weil ihre beiden Wirtsdateien in ein fremdes Kit gespiegelt sind (neu, TSK-0119, FR-0077) |
| [H140](docs/holes/H140.md) | BUG-0223 | ACCEPTED_EXCEPTION | Die Rangfolge-Prüfung urteilt über das, was der Entwurf DEKLARIERT, und der Kontrast schweigt über das, was er nicht ausrechnen kann (neu, TSK-0119, FR-0077/FR-0078) |
| [H141](docs/holes/H141.md) | BUG-0224 | VERIFIED | Der Takt-Leser ist eine Aufzählung von Adverbien (neu, TSK-0118 Nacharbeit 1, N2) |
| [H142](docs/holes/H142.md) | BUG-0225 | VERIFIED | Eine genannte Route, die auflöst und trotzdem kein Paar ergibt, bleibt rc 0 (neu, TSK-0118 Nacharbeit 1, FR-0021) |
| [H143](docs/holes/H143.md) | BUG-0226 | VERIFIED | Eine Naht, die einen TEIL der Überlappung deckt, deckt ihn weiterhin zu (neu, TSK-0118 Nacharbeit 1, FR-0021) |
| [H144](docs/holes/H144.md) | BUG-0227 | VERIFIED | Die Verengung folgt einem Verzeichniswechsel, der landet, aber nicht wirkt (neu, TSK-0116, FR-0050) |
| [H145](docs/holes/H145.md) | BUG-0228 | VERIFIED | Ein Blatt, dessen Regeln das Dokument nicht lesen darf, war für die Prüfung ein leeres Blatt — GESCHLOSSEN bis auf die verbleibende Unentscheidbarkeit (neu, Prüfung TSK-0119, FR-0077) |
| [H146](docs/holes/H146.md) | BUG-0229 | VERIFIED | Der Kontrast sah zwei Sorten Text nicht: verblasste Elemente und erzeugten Text — GESCHLOSSEN bis auf die Gruppen-Komposition (neu, Prüfung TSK-0119, FR-0077) |
| [H147](docs/holes/H147.md) | BUG-0230 | ACCEPTED_EXCEPTION | Welche Datums-Schreibweisen ein Meilenstein annimmt, entscheidet der Interpreter (neu, TSK-0117 Nacharbeit 1, DEC-0064) |
| [H148](docs/holes/H148.md) | BUG-0231 | VERIFIED | Eine Naht kann noch immer breiter sein als das, was zwei Aufträge wirklich teilen (neu, TSK-0117 Nacharbeit 1, DEC-0062) |
| [H150](docs/holes/H150.md) | BUG-0232 | VERIFIED | Ein Verzeichniswechsel, den niemand ausrechnen kann, ließ die Fege-Basis stehen (neu, Merge-Prüfung TSK-0120, N1) |
| [H151](docs/holes/H151.md) | BUG-0233 | TRIAGED | Die Erklärung, auf der Gate 5 entscheidet, liegt ausserhalb seines eigenen Schutzbereichs (neu, TSK-0121, PR-0004 AC-1) |
| [H152](docs/holes/H152.md) | BUG-0234 | ACCEPTED_EXCEPTION | Was eine Option dem Läufer antut, entscheidet kein Text (neu, TSK-0121; nach Prüfung 1 und 2 korrigiert) |
| [H153](docs/holes/H153.md) | BUG-0235 | ACCEPTED_EXCEPTION | Was der Leser nicht platzieren kann, und was er gar nicht erst sieht (neu, TSK-0121; nach Prüfung 3 erweitert) |
| [H154](docs/holes/H154.md) | BUG-0236 | VERIFIED | Die Migrationstuer schreibt einen Endzustand ohne die Evidenz, die die Kante verlangt (neu, TSK-0122) |
| [H155](docs/holes/H155.md) | BUG-0237 | TRIAGED | Die Zielklasse ist Freitext, also haengt die SR-Pflicht an einer Ausnahmeliste (neu, TSK-0122) |
| [H156](docs/holes/H156.md) | BUG-0238 | VERIFIED | Die Dispatch-Verweigerung sieht nur LAUFENDE Leases (neu, TSK-0122) |
| [H157](docs/holes/H157.md) | BUG-0239 | ACCEPTED_EXCEPTION | Kein Leser urteilt über den WORTLAUT einer Auftragszeile (neu, TSK-0123, FR-0005/FR-0010) |
| [H158](docs/holes/H158.md) | BUG-0240 | VERIFIED | Die Rückschau hat keinen Ereignis-Auslöser; der Pflichtenmelder kennt nur die Periode (neu, TSK-0123, FR-0084) |
| [H159](docs/holes/H159.md) | BUG-0241 | ACCEPTED_EXCEPTION | Der Zeigerleser der drei Rollentexte sieht nur Backticks und nur Item-Ids (neu, TSK-0123, DEC-0070) |
| [H160](docs/holes/H160.md) | BUG-0242 | TRIAGED | Ein Kit-Update MELDET den Gedächtnisbaum, den keine Rolle mehr deklariert, und entfernt ihn nicht (neu, TSK-0125, BUG-0088) |
| [H161](docs/holes/H161.md) | BUG-0243 | VERIFIED | Der Schwestertest von Gate 1 misst seine eigene Dimensionierung mit (neu, TSK-0125, BUG-0033) |
| [H162](docs/holes/H162.md) | BUG-0244 | VERIFIED | Die Last-Hälfte des Gate-3-Zeittests ist ungemessen; das Rig ist umgebaut und wartet auf ein Fenster (neu, TSK-0125, BUG-0033) |
| [H163](docs/holes/H163.md) | BUG-0245 | VERIFIED | Die Architektenschritt-Pflicht fragt das office-Kit nach einem `SR`, den es nicht kennt (neu, TSK-0126, DEC-0072) |
| [H164](docs/holes/H164.md) | BUG-0246 | VERIFIED | Ein Modulname in Backticks wird als Testzitat in ein Loch-Item geschrieben (neu, TSK-0126, DEC-0073) |
| [H165](docs/holes/H165.md) | BUG-0247 | VERIFIED | Ein positionaler GLOB innerhalb einer erklaerten Wurzel verengte nichts (neu, TSK-0126 Merge, Pruefrunde 1 B2) |
| H166 | BUG-0248 | OPEN | The docking point (scripts/invoice_intake.py) refuses a mixed-VAT-rate outgoing invoice for booking -- a ledger row carries ONE vat_rate, so a document with 7 % and 19 % positions (ordinary in trade: food beside hardware) is accepted by the norm check and then handed back 'by hand' |
| H167 | BUG-0249 | VERIFIED | The session brief does not show the rung and the effort the dispatcher derived: `report.generate_session_brief` builds each `active_tasks` row from a fixed field set (id/status/assigned_role/blocked_by), so DEC-0077 (5) and PR-0010 AC-6 ("shown in the session brief") are unbuilt while the values sit on the task item (new, TSK-0130, PR-0010 AC-6) |
| H168 | BUG-0250 | VERIFIED | One kit release ships two contradicting ladder texts: the constitutions say the escalation is derived by the kernel and "there is no user-gated escalation ladder any more", while the PMs' own SKILL and all three project_config templates still instruct the retired `sonnet-high -> sonnet-xhigh -> opus-high -> opus-xhigh/max` -- and session_status plus the scaffold still translate the retired `light` rung (new, TSK-0130, PR-0010 AC-3/AC-7, DEC-0076/DEC-0077/DEC-0078) |
| H169 | BUG-0251 | ACCEPTED_EXCEPTION | The EFFORT axis of the ladder (DEC-0077 (1)) is derived, written and shown but never applied: the Agent tool has no per-spawn effort parameter, so the child runs on its installed `effort:` pin (new, TSK-0130, PR-0010 AC-6) |
| H170 | BUG-0252 | OPEN | The office `large` effort (DEC-0078 (2): `high` when the goal's class is large) is unreachable: a `PROC` root carries no `class` field, so every office order gets the default (new, TSK-0130, PR-0010 AC-6) |
| H171 | BUG-0253 | OPEN | A project without a scaffold record -- this repository's own harness -- dispatches with `ladder: absent`: no rung is derived and no spawn is held, because there is no kit declaration to read (new, TSK-0130, PR-0010 AC-6, DEC-0078 (4)) |
| H172 | BUG-0254 | ACCEPTED_EXCEPTION | The Codex effort ceiling (`max` vs `ultra`) is unmeasured against the Codex CLI: no Codex CLI on the measuring host, the vendor's pages contradict each other, model_tiers.yaml claims no ceiling (new, TSK-0130, PR-0010 AC-2, DEC-0076 (3)) |
| H173 | BUG-0255 | ACCEPTED_EXCEPTION | On Codex the spawn-side hold of the rung does not exist: the Agent tool is not hookable there (`gen_provider_artifacts.CODEX_UNSUPPORTED_TOOLS`), so a climbed order's rung is on the lease and in the header only (new, TSK-0130, PR-0010 AC-6) |
| H174 | BUG-0256 | DUPLICATE | Doppelt zu BUG-0251: was am Spawn fehlt, ist der EFFORT -- das Modell ist waehlbar |
| H175 | BUG-0257 | ACCEPTED_EXCEPTION | Der Zeiger-Sweep kann eine ILLUSTRATION nicht von einem Zeiger unterscheiden -- und den Bestand eines fremden Stores nicht vom eigenen |
| H176 | BUG-0258 | VERIFIED | After the generation-4 hole migration docs/POST_V2_WISHLIST.md carries no `### H` entry any more, so test_repo_hygiene::test_every_hole_has_a_row_in_the_summary_and_every_row_has_a_hole is RED at HEAD b7f282e |
| H177 | BUG-0259 | VERIFIED | The empty-lists rule that keeps a kit template from shipping somebody's business reads only LISTS, so every SCALAR term of correspondence.yaml ships as a value the kit chose and a customer letter carries it unchallenged |
| H178 | BUG-0260 | OPEN | A QA fail classified narrow/mechanical still climbs the rung: the constitutions offer that classification as the alternative to escalating, and the built mechanic counts FAILED RUNS, which no classification is part of -- so the one lever the rule gave QA no longer reaches the model (new, TSK-0130, PR-0010 AC-6, DEC-0034 rule 2 vs parity matrix row 43/45) |
| H179 | BUG-0261 | ACCEPTED_EXCEPTION | Ein bestandener Test, der einen Fehler NENNT, sagt nicht, dass der Fehler weg ist -- 106 gemessene Bugs ohne Urteil |
| H180 | BUG-0262 | VERIFIED | Ein zweiter Zeitmess-Test faellt auf einem beschaeftigten Host rot statt zu ueberspringen -- dieselbe Klasse wie BUG-0033, anderer Test |
| H181 | BUG-0263 | VERIFIED | The repo-wide test-pointer check pairs backticks running across a whole file, so ONE code fence blinds it for everything below: 48 files, 39 citations, judged by nothing |
| H182 | BUG-0264 | OPEN | Four schedule claims survive in the enforcement layer that AC-1 cleaned everywhere else: .claude/hooks/gate_spawn_needs_item.py and .claude/hooks/_harness.py still say the watchers 'run on a weekly schedule', no test reads them, and the reworded watcher definitions now POINT at them (new, TSK-0130, PR-0010 AC-1, DEC-0084) |
| H183 | BUG-0265 | VERIFIED | Der Zeiger-Sweep liest in einem Projekt mit installiertem Kit die Skript-Verzeichnisse gar nicht -- auch das eigene Skript des Projekts nicht |
| H184 | BUG-0266 | VERIFIED | The project-auditor routine is REMINDED but cannot be DISPATCHED on its own route: `request-approval` offers twelve kinds and neither `routine` nor `analysis`, so the only walkable way to run the auditor is an ordinary work order with a writable allowed_scope -- measured as a process on a scaffolded dev pilot (new, TSK-0130, DEC-0084 (2)(b), confirms H111 four weeks on) |
| H185 | BUG-0268 | VERIFIED | CLAUDE.md sagt "die vier Gates dieses Repos", registriert sind fuenf -- und die Datei ist fuer jede Rolle verbotener Bereich |
| H186 | BUG-0269 | ACCEPTED_EXCEPTION | The radar watcher's Desktop scheduled task is a mechanism this repository can neither ask nor see fire: its day, hour and enabled flag live in the Desktop app, it runs only while that app is open, and a week with the app closed is silent -- the report cadence in radar/ is the only evidence, read by `--due` (corrected under DEC-0089: the task IS the mechanism and its reports DO carry the `-claude` suffix; TSK-0130, PR-0010 AC-1) |
| H187 | BUG-0270 | ACCEPTED_EXCEPTION | Der Zeiger-Sweep dieses Repos liest team-kits/ und docs/, nicht tools/ -- 39 Testzeiger in den eigenen Suiten pruefen nichts |
| H188 | BUG-0272 | OPEN | Gate 1 refuses a READ-ONLY grep as a write to the drive root when its double-quoted pattern carries escaped backticks AND a space: `grep -c "\`a\`, \`b\`" README.md` is rc 2 with 'no tool call in this repo may write C:\' (over-refusal, measured 2026-09-06 in the generation-5 merge, TSK-0133) |
| H189 | BUG-0273 | ACCEPTED_EXCEPTION | The radar claim reader admits a cadence sentence that names no mechanism word: 'The watcher duo runs once a week without a human.' passes tools/test_radar_trigger.py by design, because a claim is recognised by its WORD (schedule, automatic, cron, Desktop task, the cloud option's names, a weekday) and a cadence alone is read as intent -- so a sentence asserting agentless recurrence in plain words is judged by nobody (TSK-0133 verify round 1, P6; beside H182) |
| H190 | BUG-0274 | VERIFIED | The claim reader's list of names for the rejected cloud routine (`cloud_option.named_as`) has no tripwire at either end: the shipped README's own words for that option ('hosted code routine of the platform', 'sandbox routine against the remote') pass the reader as a mechanism claim (verify round 2 N1, TSK-0133) |
| H191 | BUG-0275 | VERIFIED | The ladder-paragraph reader's lead-in branch (`_states_the_scaling_rule`) accepts rung and effort a whole bullet apart while its docstring says a rule states both axes 'in one breath': moving the word effort into the bold lead-in and deleting the effort RULE keeps the constitution qualifying (verify round 2 N2, TSK-0133) |
| H192 | BUG-0276 | VERIFIED | A module added under tools/ shadows the team-kits module of the same name for every `python tools/<script>.py` entry point, and nothing measures the collision |
| H193 | BUG-0277 | VERIFIED | scaffold_team warns and continues when the staging carries no write_kit_state.py, so a project installs green with no hook-bundle trust recorded -- and the missing file is a kit-hash input, so every later stamp check refuses the same staging (new, TSK-0135, DEC-0092 (6) rig) |
| H194 | BUG-0278 | VERIFIED | The test-shaped-acceptance reader (`dispatch.acceptance_is_test_shaped`, DEC-0097 (2)) claims both kit languages but its negation and word lists are English-shaped: 'ein Test wird rot, ohne den Fix' is refused (`ohne` counted as a negation) and German compounds ('Regressionstest', 'Unittest') are invisible -- false negatives, the order stays on the opus default (TSK-0137 verify round 2, N-e/N-f) |
| H195 | BUG-0279 | VERIFIED | The batch route's evidence rule 'a test that NAMES the bug' (DEC-0100 (3), tools/close_measured_pass.py nodes_naming) reads an incidental mention like a measuring one: BUG-0050's only naming test says 'nothing was caught', BUG-0044's is a historical aside -- both would have been VERIFIED by a click (TSK-0138 verify round 2) |
| H196 | BUG-0280 | VERIFIED | A hook a suite starts without its own CLAUDE_PROJECT_DIR judges whatever tree the ambient variable names -- 55 of 65 call sites, and the suite cannot tell an honest one from a forgetful one |
| H197 | BUG-0281 | VERIFIED | H7 neu aufgelegt (Ausnahme nie freigegeben): `carries_work` verlangt keinen erreichbaren Endzustand — OFFEN |
| H198 | BUG-0282 | ACCEPTED_EXCEPTION | H11 neu aufgelegt (Ausnahme nie freigegeben): Ein Interpreter führt Code aus, den kein Gate lesen kann (neu, Preis des Fixes zu F2) |
| H199 | BUG-0283 | ACCEPTED_EXCEPTION | H12 neu aufgelegt (Ausnahme nie freigegeben): Ein Subagent kann sich die Ausnahme von Gate 2 selbst ausstellen |
| H200 | BUG-0284 | ACCEPTED_EXCEPTION | H16 neu aufgelegt (Ausnahme nie freigegeben): Der Pfad steht in einer Variablen, das Gate liest den Text (neu, TSK-0008) |
| H201 | BUG-0285 | VERIFIED | H21 neu aufgelegt (Ausnahme nie freigegeben): `Push-Location`/`Pop-Location` fehlen im Verzeichnis-Vokabular (neu, TSK-0011) |
| H202 | BUG-0286 | ACCEPTED_EXCEPTION | H22 neu aufgelegt (Ausnahme nie freigegeben): Die Read-only-Klassifikation gilt pro Stufe, der Pfad reist weiter (neu, TSK-0011) |
| H203 | BUG-0287 | ACCEPTED_EXCEPTION | H25 neu aufgelegt (Ausnahme nie freigegeben): Die Frist, die ein Gate sich zugesteht, und die, nach der es getötet wird (neu, TSK-0013) |
| H204 | BUG-0288 | VERIFIED | H32 neu aufgelegt (Ausnahme nie freigegeben): Ein Befehl, den eine Ersetzung einführt (neu, TSK-0019) |
| H205 | BUG-0289 | VERIFIED | H38 neu aufgelegt (Ausnahme nie freigegeben): Ein Programm, das ein Hier-Dokument einer Shell übergibt, liest keines der Gates (neu, TSK-0022) |
| H206 | BUG-0290 | VERIFIED | H39 neu aufgelegt (Ausnahme nie freigegeben): Endzustände, die dieses Repo nicht ehrlich erreichen kann: TSK `DONE`, BUG `VERIFIED` (neu, TSK-0055) |
| H207 | BUG-0291 | ACCEPTED_EXCEPTION | H40 neu aufgelegt (Ausnahme nie freigegeben): Vertragszitationen außerhalb der `.py`-Quellen von `.claude/hooks/` liest kein Stolperdraht (neu, TSK-0058) |
| H208 | BUG-0292 | ACCEPTED_EXCEPTION | H99 neu aufgelegt (Ausnahme nie freigegeben): H11 hebt die Vier-Augen-Buchung mit auf: ein Skript trägt eine ungelesene Zeile nach `HEAD` und prägt die zweite Lesung (neu, TSK-0102, FR-0065) |
| H209 | BUG-0293 | ACCEPTED_EXCEPTION | H116 neu aufgelegt (Ausnahme nie freigegeben): Die Hook-REGISTRIERUNG wird mitten in der Sitzung neu gelesen — auch zwischen zwei Werkzeugaufrufen einer Runde (neu, TSK-0108, FR-0059) |
| H210 | BUG-0294 | VERIFIED | H138 neu aufgelegt (Ausnahme nie freigegeben): Die Konformitätsbefunde des Renderers verweigern nichts: der Datensatz beantwortet eine andere Frage (neu, TSK-0119, FR-0077/FR-0078) |
| H211 | BUG-0295 | OPEN | Ein DEC-Verweis in einem Python-Docstring einer ausgelieferten Kit-Datei wird von keinem Leser beurteilt, wenn die Anfuehrungszeichen-Paarung ihn verschluckt (2 von 190, gemessen) |
| H212 | BUG-0296 | OPEN | Der mehrdeutige deutsche Genitivartikel (`der`, `einer`) beendet ein Präpositionskomplement zu früh -- eine so formulierte Verneinung kauft die billige Sprosse |
| H213 | BUG-0297 | OPEN | Die gedruckte Abhilfe des Commit-Gates dieses Repos ist rc 2, bis der Nutzer den S4-Patch fährt -- seit TSK-0144 hält ein Test in tools/ das rot, bis er gefahren ist |
| H214 | BUG-0298 | OPEN | Kit-Seite der H11-Klasse: ein Heredoc, das in einer Zeile erst in eine Datei geschrieben und dann von der Shell ausgeführt wird (`cat <<EOF > run.sh ; bash run.sh`), passiert jeden Kit-Hook |
| H215 | BUG-0299 | OPEN | Der H196-Startleser folgt einem argv, das ein Name hält, aber nicht dem PROGRAMMWORT, das erst ein lokaler Name auflöst -- heute ohne Opfer |
| H216 | BUG-0300 | OPEN | Der Stopper-Leser des Beweis-Vokabular-Tests begründet seine Unterscheidung (kann nicht zurückkehren vs. endet irgendwo) mit einer Zählung, die kein roter Test hält |
| H217 | BUG-0301 | OPEN | Der Beweis-Vokabular-Leser entschuldigt eine ganze Spanne, sobald irgendwo vor dem nächsten Backtick eine berechnete Flagge (`--%s`) steht -- eine echte Auslassung daneben bleibt stumm |

