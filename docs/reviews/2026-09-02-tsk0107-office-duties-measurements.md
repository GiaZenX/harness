# TSK-0107 (Strom G, Office) — was gemessen wurde

Alle Messungen laufen gegen die ausgelieferten Dateien des Arbeitsbaums `g2/office`, in
Wegwerf-Projekten außerhalb des Repos unter
`C:\Offline Repos\v2-testbed\_round-scratch\TSK-0107\probe\`. Wo ein Hook gemessen wird, wird der
Hook als PROZESS gestartet, mit JSON auf stdin — was eine Sitzung bekommt, ist die Ausgabe eines
Programms und nicht der Rückgabewert einer Funktion.

## 1. FR-0028 — Rückruf eines beigebrachten Verfahrens (`probe/recall_measure.py`)

Die Frage des Nutzers war: „ein Office-Team, das sich Workflows einprägt und sie mit 100 %
Zuverlässigkeit übernimmt, wie man's einmal beibringt". Gemessen wurde die Kette, die das im Kit
trägt — ein PROC-Item, die Freigabe des Nutzers darauf, und `gate_proc_approved` als das, was einen
Spawn ohne beigebrachtes Verfahren verweigert. Zwei frisch aufgesetzte Office-Projekte,
`business-a` und `business-b`.

```
STEP 0  Spawn, bevor irgendetwas beigebracht wurde         rc 2  VERWEIGERT
        ("this project has no approved procedure at all")
STEP 1  PROC-0001 erfasst (Eingangsroutine, vier Schritte)  status DRAFT
STEP 2  nach der Freigabe des Nutzers                       status APPROVED,
                                                            approved_hash 3d2d7261f8b44cf0…
STEP 3  Spawn unter dem beigebrachten PROC, Sitzung 1        rc 0  DURCHGELASSEN
STEP 4  Sitzung 2, DASSELBE Repo: das PROC steht noch        status APPROVED, Titel unverändert
STEP 5  GESTRICHEN (siehe §6.6) — der Satz, den dieser
        Schritt las, steht in JEDEM Office-Projekt
STEP 6  Spawn unter demselben PROC, Sitzung 2                rc 0  DURCHGELASSEN
STEP 7  die beigebrachten Schritte am Kernel vorbei
        geändert ("open the file" -> "skip the file")        rc 2  VERWEIGERT
        ("edited past the kernel after its approval")
STEP 8  dieselbe PROC-Id im ANDEREN Repo                     rc 2  VERWEIGERT
        ("this project has no approved procedure at all")
```

**Was das belegt.** Ein einmal beigebrachtes Verfahren überlebt den Sitzungswechsel im selben Repo
(4/6), es kann nicht still verändert werden (7), und es reist nicht in ein anderes Geschäft (8) —
genau die Klarstellung des Nutzers vom 2026-09-02, „zwei Geschäfte = zwei Repos, nichts wandert
automatisch". Der leere Zustand blockiert (0), der Weg heraus ist Erfassen + Freigabe (1/2).

**Was das NICHT belegt, ausdrücklich:** dass ein Modell dem Verfahren INHALTLICH folgt. Gemessen ist
der Apparat — dass das Verfahren da ist, dass es unverändert ist und dass ohne es kein Spezialist
startet. Ob der Text befolgt wird, ist eine Frage an eine echte Sitzung (DEC-0025-Piloten) und steht
hier nicht als beantwortet.

## 2. FR-0028 — kein ausgeliefertes Kit-Text bindet an ein Werkzeug

`tools/test_kit_neutrality.py`, gegen den ausgelieferten Baum:

* **59 Rollentexte** gelesen (drei Verfassungen, alle Agent-Definitionen über ihre GEPARSTE
  Frontmatter, alle Skills). **Ein** Fund: `team-kits/office-team/agents/shop-curator.md` — die
  Routing-`description` endet mit „…, audit, Shopify.". Eine `description` ist das, woran die
  Plattform eine Anfrage misst; dieses eine Wort macht die Shop-Rolle für den Router zur
  SHOPIFY-Rolle. Als Nahtstelle für den Rollentext-Strom eingetragen, nicht hier geändert.
* **Alle Zustandsvorlagen** des Office-Kits liefern ihre Listen leer aus; die einzige gefüllte ist
  `project_config.yaml: providers` (`claude`, `codex`) — Namen des Apparats, nichts über das
  Geschäft. Als Ausnahme mit Grund eingetragen, in beide Richtungen geprüft.

## 3. FR-0034/FR-0038 — das Fristenregister als laufender Hook

Ein Wegwerf-Projekt mit allen fünf Zuflüssen, durch den ausgelieferten `session_status.py`
(`probe/build_project.py`). Die Meldung, die dabei entsteht, nennt in einem Absatz: zwei
Aufbewahrungsjahre über der Frist, eine überfällige Wiedervorlage, eine unbezahlte Rechnung, den
fälligen Audit-Lauf und die geschlossene Steuerperiode — und in einem zweiten Absatz die zwei
Quellen, die nicht gelesen werden konnten (ein Eintrag mit einer Periode, die das Kalenderjahr nicht
teilt; eine Aufbewahrungsangabe ohne Jahreszahl). Nicht gemeldet wurden im selben Lauf: ein
Jahresordner innerhalb seiner Frist, eine bezahlte Rechnung, eine unbezahlte GUTSCHRIFT, eine
Rechnung innerhalb der Zahlungsfrist und eine Wiedervorlage in der Zukunft.

**Zeitbudget.** `_duties.TOTAL_BUDGET = 8` s. Die Summe, die der Host sieht, ist dieses Budget plus
die Git-Lesungen des Hooks (2 × 5 s, aus dem Parse-Baum des Hooks gelesen, nicht abgeschrieben) =
**18 s gegen `_compat.HOOK_DEADLINE_SECONDS = 60`**. Gemessen als Prozess über ein Projekt in der
Größe der eigenen Obergrenzen des Registers (200 Ablageregeln × 10 Jahresordner, 4 000 Ledgerzeilen,
200 Registereinträge): **2,17 s** für den ganzen Sitzungsstart.

## 4. Der Apparat-Befund dieser Runde

`request-approval` kann die Freigabe-Arten `routine` und `analysis` nicht anlegen, auf denen die
Auditor-Routine laut aller drei Verfassungen reitet. Messung, Folge und Urteil stehen als `H111` in
`docs/POST_V2_WISHLIST.md`; `H112` und `H113` tragen die zwei benannten Grenzen des Registers.

---

## 5. Nachtrag der Übernahme-Runde (2026-09-02, zweiter Lauf)

Der erste Lauf wurde durch einen Nutzer-Stopp beendet. Der zweite hat seinen Stand geprüft statt
geglaubt; was dabei zusätzlich gemessen wurde, steht hier. Jede Zeile hat einen Test, der ohne den
Fix rot wird, und jedes Rot ist in einer Kopie außerhalb des Repos gesehen worden.

### 5.1 Ein Testzeiger, der ins Leere zeigte

`_duties.py` schrieb die Budget-Rechnung der Datei `tools/test_hooks_v2.py` zu, unter dem Namen
`test_the_session_start_budgets_together_fit_inside_the_hook_deadline`; der Test liegt in
Wahrheit in `tools/test_office_duties.py::test_the_session_start_budgets_together_fit_inside_the_hook_deadline`. Der Satz
las sich als gemessen und schickte einen Leser in die falsche Datei. Gebaut wurde daraus die
Eigenschaft statt der Korrektur: `tools/test_repo_hygiene.py::test_every_test_pointer_this_repo_writes_resolves`
liest jede voll qualifizierte Knoten-Id (`datei.py::name`) aus den Backtick-Spannen von `team-kits/`
und `docs/` und löst sie im Syntaxbaum der genannten Suite auf.

```
über team-kits/ allein, vor der Reparatur   : 122 geprüft, 1 unauflösbar (_duties.py:52)
über team-kits/ + docs/, nach der Reparatur : 184 geprüft, 0 unauflösbar
```

Die zeilenweise Spannen-Lesung des Nachbarn `_DELIMITED_RX` hätte 0 gefunden — die eine echte
Fundstelle ist über zwei Zeilen umgebrochen. Das ist im Kommentar an `_CODE_SPAN_RX` festgehalten.

Zweiter Fund derselben Klasse: die neuen Löcher `H111`–`H113` nannten ihre Tests **unqualifiziert**,
und `.claude/hooks/test_gates.py::test_every_test_a_hole_names_is_one_that_exists` löst einen
unqualifizierten Namen ausschließlich in `test_gates.py` auf (der Test hieß am 2026-09-02 noch
`test_every_test_the_hole_list_names_is_one_that_exists`; die Umbenennung kam mit der Migration
der Löcherliste in typisierte Items). Gemessen: der Lauf
`pytest .claude/hooks/test_gates.py -k "hole or measurement or reference"` war **1 failed, 7 passed**
(„H112 names `test_a_rotated_event_log_…`, and 0 tests in test_gates.py answer to it"), nach dem
Qualifizieren **8 passed**.

### 5.2 F6 — die `dir/*`-plus-Negation-Falle, jetzt gemessen

Die `.gitignore`-Vorlage des Office-Kits trug beide Hälften von F6 bereits; **gemessen** war nur die
DSGVO-Hälfte. Neu ist `tools/test_hooks_v2.py::test_the_office_gitignore_still_lets_the_tray_seeds_into_a_fresh_clone`:
die Ablagen kommen aus `kernel.trays`, die Seeds sind die Dateien, die unter ihnen wirklich
ausgeliefert werden, und entschieden wird mit `git check-ignore` in einem Wegwerf-Repo.

```
Mutation (außerhalb des Repos): inbox/* archive/* outbox/*  ->  inbox/ archive/ outbox/
Lauf:  FAILED  "archive/README.txt is a file the kit SHIPS and the .gitignore hides it"
zurückgesetzt: passed
```

### 5.3 H112(b) — der aufgebende Lauf, als Kette gefahren

Argumentiert war die Grenze aus dem Code; gemessen ist sie jetzt. Beide ausgelieferten Hooks als
Prozesse auf derselben `SubagentStop`-Nutzlast, danach das ausgelieferte `_duties` befragt — die
Ausgabe steht bei `H112` in `docs/POST_V2_WISHLIST.md`. Kurz: `gave_up` und `subagent_stop` landen
im selben Log, die zweite Zeile löscht die Wochenmeldung, die erste sagt, dass nichts geliefert
wurde, und niemand verbindet sie.

### 5.4 „Das Kit verschickt nichts" — ein Versprechen der Vorlage, jetzt eine Eigenschaft

`business_profile.yaml` verspricht dem Nutzer bei den Zahlungszielen, dass das Kit nichts
verschickt. Gebaut ist das jetzt: `tools/test_hooks_v2.py::test_the_office_kit_ships_nothing_that_could_send`
liest die Importe aller 44 ausgelieferten Python-Module des Office-Kits aus dem Syntaxbaum. Beide
Enden — der Leser muss einen gepflanzten Import sehen, und das Versprechen muss in der Vorlage
stehen, sonst ist der Test eine Regel über nichts.

```
Mutation (außerhalb des Repos): `import smtplib` an scripts/ledger_add.py angehängt
Lauf:  FAILED  "... these shipped modules can reach off the machine:
                {'…/scripts/ledger_add.py': ['smtplib']}"
```

### 5.5 Eine Zahl, die zwei Dinge sagte

`MAX_LEDGER_YEARS = 12` trug einen Kommentar, der die Zahl **zehn** begründete („die längste
gesetzliche Frist, die die Aktenplan-Vorlage nennt"). Die Begründung ist ersetzt durch die, die
zutrifft — eine Kostengrenze für den Sitzungsstart —, und die Zahl wird jetzt an beiden Enden
gemessen statt behauptet: `tools/test_office_duties.py::test_the_receivable_feed_opens_the_years_its_own_bound_names`
legt ein Ledger EIN Jahr tiefer als die Grenze an und prüft, dass das Jahr knapp innerhalb gelesen
und das knapp außerhalb nicht gelesen wird.

Dabei kam die zweite Hälfte heraus: die Maximal-Messung des Sitzungsstarts war in der **billigen**
Richtung gebaut. Jeder Zufluss kehrt bei `MAX_PER_FEED` zurück, also ist ein Ledger voller offener
Rechnungen nach 200 Zeilen fertig. Der teure Fall ist das ruhige Ledger: es hat keinen Ausstieg und
wird bis zur letzten Zeile des letzten erlaubten Jahres gelesen. Die Messung trägt jetzt bezahlte
Zeilen in allen Jahren, die unbezahlten nur im ältesten, und beweist mit einer eigenen Zusicherung,
dass das tiefste Jahr wirklich geöffnet wurde.

### 5.6 Drei Sätze, die mehr behaupteten, als der Baum trägt

* `_duties.py` und ein Testdocstring schrieben `BUG-0068` zu, dass dort „ein echter Backlog gelöscht"
  worden sei. Das Item hält das nicht fest (es beschreibt eine Sackgasse beim Vorlagen-Abgleich und
  eine überstellte Liste). Der Satz zeigt jetzt auf die Stelle, an der das Kit dieselbe Unterscheidung
  schon zieht (`session_status.main`, Meldung „KIT MERGE BACKLOG UNREADABLE"), statt eine Folge zu
  behaupten. Der Satz IM ausgelieferten `session_status.py` der drei Kits sagt dasselbe seit
  Längerem — das ist eine Naht, keine Änderung dieses Stroms.
* Die Aktenplan-Vorlage berief sich auf „eine Erhebung des Office-Kits am 2026-08-31", die es als
  Dokument nicht gibt. Sie sagt jetzt schlicht, was zutrifft: kein primärer Gesetzestext wurde
  gelesen und keiner wird mitgeliefert.
* Dieselbe Vorlage bezifferte die Eingang/Archiv-Grenze mit „zwei Fassungen"; das Felddokument sagt
  „mehrere Fassungen (v1.2 → v1.9)". Die Zahl ist raus.

---

## 6. Nachtrag der Neuauflage (2026-09-02, `TSK-0113` nach dem Prüfbericht zu `TSK-0107`)

Der Prüfer gab das Paket mit 13 Paket- und 3 Item-Befunden zurück. Der Auftrag wurde neu
geschnitten (`TSK-0113`, plus `TSK-0112` für den kit-unabhängigen Teil); dieser Abschnitt trägt
nur, was in diesem Lauf gemessen wurde. Arbeitsverzeichnis
`C:\Offline Repos\v2-testbed\_round-scratch\TSK-0113\`.

### 6.1 P1 — das Register häufte Vergangenheit an, und der Absatz verlor die Steuerfrist

Der Kopfkommentar von `_duties.py` versprach, jeder Zufluss melde „die AKTUELLE Pflicht … und
niemals angehäufte vergangene". Gemessen war das falsch. Ein Archiv mit einem Jahresordner je
Geschäftsjahr seit 2005 unter EINER Aufbewahrungsregel, dazu eine monatliche Voranmeldung, durch
den ausgelieferten `session_status.py` als Prozess:

```
vorher : 15 Pflichten, 13 davon Vergangenheits-Jahresordner derselben Regel
         der Absatz nennt 2005…2010 und bricht ab; die Voranmeldung kommt darin NICHT vor
nachher: 3 Pflichten, davon EINE Aufbewahrungspflicht (13 Jahresordner, aeltester 2005)
         der Absatz nennt die Voranmeldung und die Aufbewahrungspflicht
```

Zwei Hälften, beide gebaut: `retention_duties` fasst je REGEL zu einer Prüfpflicht zusammen
(ältestes Jahr + Anzahl), und `briefing` vergibt seine Plätze reihum je QUELLE statt streng nach
Datum (`_named_fairly`). Die Mutationsläufe zeigen, dass jede Hälfte für sich schon reicht, damit
die Ende-zu-Ende-Messung wieder grün wird — rot war sie am unreparierten Baum, wo beide fehlten:

| Mutation im Klon außerhalb des Repos | Ende-zu-Ende (Absatz nennt die Steuerfrist) | eine Pflicht je Regel | kein Zufluss verdrängt einen anderen |
|---|---|---|---|
| `_named_fairly` → `duties[:MAX_NAMED]` | passed | — | **failed** |
| Sammeln je Regel → eine Pflicht je Jahr | passed | **failed** | — |
| beide (= der vorgefundene Baum) | **failed** | **failed** | **failed** |

### 6.2 P2 — die Aktenplan-Vorlage lieferte unlesbare Aufbewahrungsangaben aus

`FP-900` und `FP-901` trugen Prosa ohne Jahreszahl, also meldet `_retention_years` sie als
unlesbar — bei JEDEM Sitzungsstart eines Projekts, das dem Beispielblock folgt. Sie tragen jetzt
`retention: null` mit dem Grund daneben, ebenso `FP-002`, dessen Frist erst mit dem Ende eines
Produktlebens zu laufen beginnt. Gemessen wird die Vorlage jetzt so, wie ein Nutzer sie benutzt:
der Beispielblock wird ENTKOMMENTIERT und als YAML GEPARST, und jede Regel muss den Schlüssel
tragen und entweder lesbar oder leer sein
(`tools/test_office_duties.py::test_every_retention_the_filing_plan_template_ships_is_readable_or_deliberately_empty`).
Rot mit einer gepflanzten unlesbaren Angabe; die Gegenrichtung ist die Zusicherung, dass mindestens
eine Regel noch eine lesbare Spanne zeigt.

### 6.3 P3 — ein Absolutsatz über eine Wand, die weniger kann

Die Vorlage schrieb, `guard_fs_tripwire` verweigere „every shell deletion under `archive/` and
every move out of it". Gegen einen installierten Office-Projekt-Klon mit einem echten Dokument
unter `archive/finance/2026/invoice.pdf`, jede Zeile als PreToolUse-Nutzlast an den ausgelieferten
Hook:

```
rc=2  rm -f archive/finance/2026/invoice.pdf
rc=2  mv archive/finance/2026/invoice.pdf ../x.pdf
rc=0  find archive -name *.pdf -delete
rc=0  python -c import os; os.remove(archive/finance/2026/invoice.pdf)
rc=0  tar -cf out.tar --remove-files archive/finance/2026/invoice.pdf
```

(die drei rc-0-Zeilen oben ohne ihre Quotierung wiedergegeben, damit die Tabelle lesbar bleibt;
gefahren wurden sie wörtlich wie im Rig `_round-scratch/TSK-0113/tripwire.py`.)

Die Vorlage sagt jetzt, was die Regel des TEAMS ist, und schickt für die Wand an den Kopf des
Wächters, statt seine Liste ein zweites Mal zu führen. Ein Löschen, das eine FLAGGE statt eines
Verbs verlangt, stand in keiner der beiden Lesungen des Wächters und in keiner seiner Grenzlisten —
es steht jetzt mit dieser Messung in seinem eigenen „WHAT THIS DOES NOT SEE".

### 6.4 P6 — die Eindämmung wurde an der Schreibweise abgelesen statt aufgelöst

`_literal_prefix` verwarf einen Laufwerksbuchstaben nur in der ERSTEN Pfadkomponente, und
`os.path.join` lässt eine spätere gewinnen:

```
a/b/D:/<year>/   ->  prefix a/b/D:  ->  os.path.join(root, a, b, D:)  ->  D:
```

Ein Sitzungsstart hätte dort das aktuelle Verzeichnis eines anderen Laufwerks aufgelistet. Ersetzt
durch `_project_directory`, das den Pfad AUFLÖST und gegen die Projektwurzel hält
(`os.path.commonpath`; ein `ValueError` bei getrennten Laufwerken heißt „draußen"). Der Test fährt
jede Klasse: Klettern, absolut, Laufwerk vorn, Laufwerk hinten, UNC, gemischt — plus die Kontrolle,
dass eine gewöhnliche Regel weiterhin auflöst.

### 6.5 P5, P7, P10 — drei Sätze auf das Gemessene gebracht

* **P5.** Der Kommentar an `MAX_LEDGER_YEARS` sagte, ein stilles Senken der Zahl werde rot.
  Gemessen: die Zahl von 12 auf 11 gesenkt → **passed** (der Test misst sein Ledger an der
  Konstante); den Ausschnitt `years[:MAX_LEDGER_YEARS]` auf `years[:2]` geändert → **failed**. Der
  Kommentar sagt jetzt genau das.
* **P7.** Der Korpus von `test_the_office_kit_ships_nothing_that_could_send` ist das KIT: 44
  Module, 0 erreichende Importe. Ein INSTALLIERTES Projekt trägt 68, darunter
  `.claude/kernel/lock.py` mit `import socket` für `gethostname()`. Der Kernel liegt außerhalb
  dieses Stroms; der Docstring benennt ihn jetzt als gemessenen, ungeprüften Rest, statt den Korpus
  still zu erweitern. Die beiden Zahlen stehen hier und im Rundenprotokoll, nicht in einem zweiten
  Kommentar.
* **P10.** `session_status.py` schluckte jeden Fehler beim Laden des Registers. Mit weggenommenem
  `_duties.py` erschien der Absatz einfach nicht — ein Manager liest das als Geschäft ohne Fristen.
  Jetzt steht dort eine Zeile „DUTY REGISTER UNAVAILABLE (…)", gemessen an einer KOPIE des
  ausgelieferten Hooks, der das Nachbarmodul fehlt.

### 6.6 P9 — ein Schritt der Rückruf-Messung, der nicht scheitern konnte

STEP 5 prüfte, ob eine bestimmte Zeichenkette in der Sitzungsstart-Meldung steht. Das ist ein
Literal aus `session_status.py`, das in jedem Office-Projekt gedruckt wird. Gemessen an einem
Projekt, dem NICHTS beigebracht wurde:

```
STEP 5  GESTRICHEN. das Literal des alten Schritts steht auch in einem Projekt, dem nichts
        beigebracht wurde:                                              JA
        der erzeugte session_brief.yaml nennt das gelehrte PROC-0001:   NEIN
```

Der Schritt ist aus der Belegkette gestrichen. Die zweite Zeile ist der Grund, warum er nicht
einfach umgehängt wurde: `kernel.report.generate_session_brief` baut überhaupt keinen
PROC-Abschnitt — eine Naht an Strom F, kein Befund gegen dieses Kit. Die übrigen Schritte
(0/1/2/3/4/6/7/8) sind unverändert und tragen die Aussage weiter.

### 6.7 P8 — Neutralität, jetzt auch über Vorlagen und über den Piloten

Der Rollentext-Leser nimmt eine Plattform in einer QUOTIERTEN Spanne bewusst aus: in Prosa ist ein
Name in Anführungszeichen der Gegenstand des Satzes. Eine VORLAGE ist keine Prosa — sie wird in das
Repository des Geschäfts kopiert, wo ein quotierter Beispielwert der Wert ist, mit dem das Feld
ankommt. Die Vorlagen werden deshalb als ROHE ZEILEN gelesen, ohne jede Ausnahme. Drei Fundstellen,
alle neutralisiert: eine Beispielliste von Verkaufskanälen mit zwei Marktplatznamen, ein
Beispielwert für die Herkunft der Umsatzdaten mit einem Shopsystem-Namen, und ein Beispiel für
Namensvereinheitlichung, das aus einer echten Marktplatz-Tochter gebaut war.

Dazu die zweite Klasse: der PILOTBETRIEB, aus dem dieses Kit erhoben wurde, wird aus der Erhebung
selbst gelesen (`docs/office-kit-from-field.md`) statt hier getippt, und darf in keinem
ausgelieferten Text stehen — weder in einer Vorlage noch in einem Rollentext. Beide Enden gemessen
(gepflanzter Plattformname in einem Kommentar, gepflanzter Pilotname in Vorlage und Rollentext: je
rot). **Was der Test nicht kann**, steht als Grenze im Protokoll und nicht hier als Anspruch: „ist
dieses Wort eine Produktgruppe" ist Weltwissen; das Kit liefert heute keine, und ein Rollentext,
der eine in eigener Prosa nennt, ohne einen der bekannten Namen zu benutzen, wird nicht gefunden.

### 6.8 P11 — die Tagesgrenze, in jedem Zufluss

Sechs Messungen am Stichtag selbst, je eine Mutation im Klon außerhalb des Repos, alle rot:
`is_overdue` zählt den Fälligkeitstag selbst als überfällig; der Steuer-Zufluss schließt einen
Monat schon an seinem letzten Tag; die Aufbewahrung läuft am 31.12. selbst ab; eine Rechnung wird
am letzten Tag des Zahlungsziels gemahnt; eine Wiedervorlage ist am Tag selbst überfällig; die
Routine rechnet sieben Tage statt einer ISO-Woche.

### 6.9 Kosten eines Sitzungsstarts, in der Richtung ohne Frühausstieg

200 Ablageregeln × 10 Jahresordner (2 000 Jahresordner), 200 Registereinträge, jedes erlaubte
Ledgerjahr voll, der ausgelieferte Hook als Prozess:

```
alle Jahresordner UEBER der Frist  (200 Pflichten, Kappe erst bei der letzten Regel)  0,84 s
kein Jahresordner ueber der Frist  (0 Pflichten, gar kein Ausstieg moeglich)          0,92 s
Schranke: _compat.HOOK_DEADLINE_SECONDS = 60 s
```

Durch das Sammeln je Regel ist die teure Richtung jetzt der Normalfall der Messung: 200 Regeln
ergeben höchstens 200 Pflichten, die Kappe greift also frühestens bei der letzten Regel, und jede
Regel wird wirklich aufgelistet.

### 6.10 FR-0076 — die Rechtsform, benannt statt geprüft

`business_profile.yaml` bot als Beispiele auch Kapitalgesellschaften an, während das Kit
ausschließlich für die Einnahmenüberschussrechnung gebaut ist und für Buchführungspflichtige
bewusst nichts baut (`FR-0076`). Die Beispiele nennen jetzt nur noch die EÜR-Formen; der Text sagt,
wer nicht dazugehört (Kapitalgesellschaften ab dem ersten Tag, andere ab den Schwellen des § 141
AO), dass keine primäre Quelle gelesen wurde, und ausdrücklich, dass NICHTS den Wert prüft. Der
letzte Satz ist eine Eigenschaftsbehauptung und deshalb ein Test:
`tools/test_hooks_v2.py::test_no_shipped_office_module_decides_anything_on_the_legal_form` liest
jeden ausgelieferten Modul-Syntaxbaum des Kits; beide Enden rot gemessen (ein gepflanzter Leser,
und der gelöschte Satz in der Vorlage).

---

## Nachtrag 2026-09-11 (TSK-0133, Merge Generation 5) — H181

Dieses Protokoll ist eines der Dokumente, an denen `BUG-0263` (H181) die Blindstelle des
repo-weiten Zitat-Lesers gemessen hat: unterhalb seines ersten Codezauns nennt es zwei Testknoten,
die kein Leser dieses Repos beurteilt und die auf nichts auflösen (beide seither umbenannt; das
Item führt sie beim Namen, hier stehen sie absichtlich nicht noch einmal als Zitat — ein zweites
totes Zitat außerhalb des Zauns wäre der nächste Befund). Die Messungen oben sind unverändert;
korrigiert wird hier nichts, das Item trägt die Zahl und die Reparaturdistanz.
