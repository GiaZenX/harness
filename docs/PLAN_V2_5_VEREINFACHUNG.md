# Plan: Vom bremsenden zum effizienten Agentensystem („V2.5", kein V3)

## Kontext

Seit Wochen wächst das System in die Breite: 86.000 Zeilen Code, 102.000 Zeilen Tests, 213 Löcher,
122 Entscheidungen, 40+ Kit-Versionen in 16 Tagen. Das unabhängige Gutachten
(`project_memory/staging/FR-0089/independent-review-2026-09-27.md`) und deine Beobachtungen in synaipse
sagen dasselbe: Der Kern ist gut, aber das System bremst sich selbst – Befehlszeilen-Schutzregeln
blockieren Harmloses, Freigaben kommen als kryptische Einzelfragen mitten in der Arbeit, der PM baut
in winzigen seriellen Häppchen, Dateien werden über viele Runden immer wieder angefasst.

Der Plan ist durch eine unabhängige Gegenprüfung gegen die Entscheidungen (DECs) gelaufen: zwölf
Korrekturen sind eingearbeitet (u. a. feste Größengrenzen statt Löschen, Kernel-Schreibprotokoll muss
erst gebaut werden, Gesamtlauf nach jeder Zusammenführung bleibt Pflicht).

Ziel dieses Plans: **erst ein gemeinsames Verständnis, dann eine Bestandsaufnahme, dann ein
Umbau in parallelen Blöcken** – mit laufender Messung, was hilft und was bremst. Es ist **kein V3**:
Kernel, Projektakte, Items-Hierarchie, Freigabe-Garantie und Bauer/Prüfer bleiben; umgebaut wird die
Schutzschicht, der Freigabe-Ablauf, das Verhalten des PM und die Textmenge.

---

## 1. Gemeinsames Verständnis: Was soll das Agentensystem können?

**Auftrag in einem Satz:** Aus einem gemeinsam freigegebenen Plan liefert ein Team von KI-Agenten
selbstständig, parallel und nachweisbar geprüft fertige Software – der Nutzer entscheidet *was*,
das System erledigt *wie*, und nichts geht verloren.

**Was es gut können muss (daran wird alles gemessen):**
1. **Gemeinsames Verständnis herstellen** – Plan zu Beginn, Verständnis-Karte bei Änderungswünschen,
   Abnahme-Rundgang am Ende. Karten lesbar, deutsch, mit PM-Erklärung.
2. **Autonom und parallel abarbeiten** – der PM entscheidet selbst, wie viele Bauer (z. B. 2 Frontend,
   5 Backend), was gleichzeitig läuft, in großen Blöcken; neue Änderungswünsche fließen direkt in die
   laufenden Blöcke ein, wo sie hingehören.
3. **Qualität nachweisen** – getrennter Prüfer, „erst rot, dann grün", Prüfung am Ende eines Blocks,
   nicht nach jedem Häppchen.
4. **Nichts vergessen** – Projektakte + Taskboard: PR → SR → TSK, CR → SR/TSK, FR, BUG; jede
   Entscheidung, jeder Beweis.
5. **Effizient mit Tokens und Zeit** – kein Polling, keine Wiederholungs-Runden durch Blockaden, Tests
   gezielt, eine Datei einmal mit allen Änderungen anfassen.

**Die harten Garantien (per Mechanik durchgesetzt, nicht per Text):**
- G1 Nur der Kernel schreibt die Projektakte.
- G2 Ein Agent startet nur mit einem Auftrag (Item).
- G3 Eine Freigabe entsteht nur aus der echten Antwort des Nutzers.
- G4 Kein Commit/Merge ohne Prüfurteil; kein Push ohne Nutzer.
- G5 Bauer ≠ Prüfer.
- G6 Keine Zerstörung fremder/ungesicherter Daten.

Alles andere ist Hilfe, keine Garantie – und muss mehr bringen, als es bremst.

---

## 2. Bestandsaufnahme: bleibt / vereinfachen / weg / neu

| Baustein | Entscheidung | Warum (Beleg) |
|---|---|---|
| Projektakte + Kernel als einziger Schreiber | **BLEIBT** | Herz des Systems (G1); Gutachten: „unbedingt schützen" |
| Items-Hierarchie + Taskboard | **BLEIBT, sichtbarer** | dein Kernwunsch; Board zeigt PR/SR/CR/TSK-Kette |
| Auftrag nur mit Item (G2), parallele Ströme | **BLEIBT, aktiv nutzen** | Ströme halbierten Wartezeit (DEC-0102); im Feld nie genutzt |
| Freigabe-Garantie (G3) | **BLEIBT** | alle 26 synaipse-Freigaben echt |
| Freigabe-Ablauf (15 Arten, Einzelfragen, kryptisch) | **VEREINFACHEN** auf ~6 Arten, 3 Momente | DEC-0119/0123; Stream A von Order 7 (ruhige Karte, Sammelkarte) schon gebaut |
| Invarianten-Gates (Commit/Spawn/Push/Freigabe) | **BLEIBT** | klein, fangen echte Fehler |
| Befehlszeilen-Zerlegung: **nur das Erraten des Schreibziels** in Shell-Zeilen (gate_write_scope, _compat, _harness) | **ERSETZEN** durch ein neues Kernel-**Schreibprotokoll** (Pfad + Prüfsumme je Schreibvorgang) + Kontrolle bei Stop und vor jedem Commit; `permissions.deny` nur zusätzlich und erst nach Messung (Windows, bypass-Modus, Codex) | ~¼ aller Löcher, tägliche Fehlblockaden; Gegenprüfung: das Protokoll existiert noch nicht → muss erst gebaut werden |
| Write/Edit-Pfadprüfung in gate_write_scope | **BLEIBT** | exakt (Pfad ist eigenes Feld), billig, anbieterneutral |
| Git-/Push-/Docker-/Testlauf-Erkennung in _compat (gate_git, gate_push_token, gate_shell_hygiene, Gate 5) | **BLEIBT** | hält G4/G6; echter Vorfall: gestoppte Produktionsdatenbank eines Nachbarprojekts |
| **NEU: Nachkontrolle Freigaben** | **BAUEN**: jedes neue APR passt zu einer echten Antwort in der Sitzungsmitschrift | ersetzt die Wand gegen gefälschte Freigaben (H80), die mit der Zerlegung wegfällt |
| Modell-Leiter | **NEU ZUSCHNEIDEN**: 4 anbieterneutrale Stufen nach Arbeitsgröße, PM wählt je Auftrag (siehe §4 Strom C, Recherche) | dein Vorschlag + Recherche |
| Prüfschleifen (Bauer/Prüfer, rot-zuerst, Mutation) | **BLEIBT**, aber nur Verhalten blockiert; Textbefunde gesammelt am Ende; Prüfung je Block | stärkster Qualitätshebel |
| Laufzeit-Leser, die Sprache beurteilen (Verneinungen, Preise) und Tests „steht Satz X im Regeltext" | **WEG** | DEC-0112/0116 schon beschlossen; kosteten Runden |
| „Ein Test nennt den Fehler" (DEC-0100) | **BLEIBT als feste Verknüpfung** Beweis → Testname, kein Wortleser | hat zwei falsche Abschlüsse verhindert (BUG-0044/0050) |
| Verweisprüfung in `validate.py` (§-Nummern, Pfade lösen auf) | **BLEIBT** | billig, fängt kaputte Verweise nach der Diät |
| Größen-Rekord (heute „≤ Rekord", Lead hebt selbst an → 30 → 63 KB durchgewunken) | **ERSETZEN** durch eine **feste Obergrenze** auf dem Stand nach der Diät; anheben nur **du** per DEC; Überschreiten = harter Fehler | deine Sorge vor Wachstum; die alte Sperre hielt nichts |
| **NEU: feste Grenze je Rollen-Skill** | **BAUEN** | PM-Skill (54 KB) hat heute gar keine |
| Abschnitts-Pins | **EINMAL NUTZEN, DANN WEG**: in der Diät als Prüfliste (jeder Abschnitt: behalten / verschoben / gestrichen mit Grund), danach löschen; 682-KB-Pin-Journal archivieren | gebaut gegen stilles Streichen bei großen Kürzungen – genau der Diät-Moment |
| Verfassung + PM-Skill | **TEXTDIÄT**, vorher messen, was wirklich beim Start geladen wird (~63 KB statt 117?) | PM befolgt Kernregeln trotz Text nicht |
| Kernel-Größengrenzen (Ergebnis 4 KB, Sitzungsübersicht 25 KB, Item 12 KB) | **BLEIBT** ausdrücklich | Wachstumsbremse, die hält |
| Handwerks-Gedächtnis je Rolle | **BLEIBT mit harten Grenzen**; Aufräum-Tür (`upkeep prune-memory`, Order 7); Nummern-Regel sperrt nur **neu hinzugefügte** Item-Nummern | die Sackgasse war die Alles-auf-einmal-Nummernregel, nicht das Budget |
| Watcher | **BLEIBT und wird BREITER** (deine Entscheidung): unsere Nachrichtenquelle. Zwei Teile je Bericht: (1) „Was bringt es unserem Repo?" mit konkreten Vorschlägen, (2) „Was hat sich insgesamt getan?" – auch Dinge, die auf den ersten Blick nicht passen (z. B. Claude Design in Claude Code), mit einem zweiten Blick „könnte das uns helfen?"; dazu die Pflichtfrage bei neuen Modellen (Leiter-Tausch nur mit Messbeleg) und die Pflege der Datei „welches Modell wofür" | fand Opus 5.5, AGENTS.md nativ, GPT-6 |
| Werkstatt dieses Repos | **VERSCHLANKEN wo es bremst** – laufend gemessen (§5) | deine Entscheidung heute |
| Test-Suite (1–2 h Gesamtlauf) | **TEILEN**: schneller Kern < 10 min je Runde; **Gesamtlauf verpflichtend nach jeder Zusammenführung vor dem Commit** (dort fand er echte Fehler: DEC-0063, 0070, 0080), bei Einzelaufträgen vor Lieferung/CI | Effizienz ohne Verlust |
| **NEU: DEC-Ablöse-Liste** | **BAUEN**: jeder gestrichene Baustein nennt die DEC, die er ablöst; Regel „eine neue Regel nur gegen eine gestrichene"; DEC-0056 (Löcher brauchen deine Ausnahme) wird für Werkstatt-Löcher per neuer DEC abgelöst | heute werden Regeln nur hinzugefügt |
| Behalten ausdrücklich | DEC-0026 (nichts löschen, nach C:/Trash), DEC-0056 (c), Protokoll laufend (DEC-0116/0121), günstige Stufe nur mit Test-Abnahme (DEC-0097/0112), Nacharbeit nicht auf oberster Stufe (DEC-0063 (3)), mechanische Fehlschläge steigen nicht (DEC-0107), Prüfer bleibt Opus | hart erlernt |
| **NEU: Frontend-Prüfung** (Kommentar-Werkzeug aus synaipse PR-0031) | **ÜBERNEHMEN** ins Dev-Kit + Freigabe-Sperre bei offenen Kommentaren | FR-0094, in synaipse fertig |
| **NEU: Abnahme-Rundgang am Ende** | **BAUEN** | DEC-0123 |
| **NEU: Kosten-/Fortschrittssicht** | **BAUEN** (Board: geliefert / in Arbeit / wartet auf dich / Verbrauch) | Gutachten §5 |

---

## 3. Antworten auf deine Fragen

- **Funktionieren die gezielten Tests?** Größtenteils ja: Gate 5 verweigert den vollen Lauf außer mit
  `DELIVERY_RUN=<Item>`, Bauer fahren nur betroffene Gruppen, der Gesamtlauf einmal vor dem Commit.
  Schwachstelle: der Gesamtlauf dauert 64–134 min und hat in 3 von 3 Aufträgen nichts gefunden, was der
  Prüfer übersehen hatte → teilen (schneller Kern / voller Lauf in CI).
- **V3 oder kleine Anpassungen?** Mittel: kein Neubau. Der größte Teil ist **Rückbau** (Zerlegung,
  Prosa-Prüfer, Text) plus vier gezielte Neubauten (Rundgang, Frontend-Prüfung, Stufen, Board-Sicht).
- **Warum hat synaipse noch P0–P12?** Die Ziele *sind* dort PR-0018 … PR-0030; „P0"…„P12" steht nur
  noch als Präfix im **Titel** (Überbleibsel des alten Masterplans). Korrektur: Titel beim nächsten
  Plan-Rundgang ohne Präfix (ein Umbenennen jetzt würde bestehende Freigaben ungültig machen).
- **Eine Datei einmal statt über viele Runden / CRs direkt einbauen:** wird PM-Regel **und** Mechanik
  (Strom C): Aufträge je Block, der Kernel meldet beim Anlegen „diese Dateien sind schon in Block X" →
  anhängen statt neuer Auftrag; neuer CR landet im laufenden Block, dessen Dateien er berührt.
- **Polling auf null, stattdessen Lebenszeichen:** Niemand schaut mehr periodisch nach. Jeder lange
  Lauf (Testlauf, Unteragent, Hintergrundbefehl) gibt **selbst regelmäßig ein Lebenszeichen** ab (z. B.
  eine Zeile mit Zeitstempel und Fortschritt in eine Herzschlag-Datei bzw. als Ereignis). Bleibt es länger
  als eine festgelegte Frist aus, gilt der Lauf als **hängend oder gescheitert** – der Wartende wird
  benachrichtigt statt ewig zu warten; die Abschlussmeldung beendet das Warten im Normalfall.
  Unteragenten fahren lange Läufe mit Zeitlimit (BUG-0313-Lehre). Heute gemessen: 6 % Polling, und zwei
  Läufe hingen still bis zu 37 Minuten.

---

## 4. Umsetzung – parallel in Wellen

### Welle 0 (sofort, parallel)
- **0a Order 7 abschließen:** unabhängiger Prüfer auf den Merge TSK-0156 → Gesamtlauf nach PASS →
  Commit, Push, Verteilung → dein Patch 4 (FR-0093-Zeile + H47). *(Merge ist fertig, 4 Stempel.)*
- **0b Ausgangswerte messen** (für §5): Tokens je Auftrag (`tools/measure_agent_tokens.py`),
  Fehlblockaden je Sitzung (Gate-Verweigerungen aus `.audit/hook_events.jsonl`), Klicks je Ziel,
  Prüfrunden je Auftrag, Produkt- vs. Buchführungs-Commits – hier **und** in synaipse.
- **0c Modellstufen-Recherche** (läuft: wie Anthropic, OpenAI, Aider, Cursor, Cline, OpenHands und
  Praktiker Modell + Denktiefe nach Aufgabe staffeln; Bewertung deines Vorschlags „Sonnet high / Opus
  low / Opus high / Opus xhigh" als neutrale Stufen Mikro … Makro; Regel, welche Stufe neue Modelle
  ablösen) → ich lege dir die Stufentabelle **vor Welle 1** als eine Entscheidungsfrage vor.

**Ergebnis der Recherche 0c (2026-09-27; Anthropic-Blog 07.07.2026, Codex Prompting Guide, Aider
Architect-Modus, Cursor Router, Cline Plan/Act, RouteLLM, Studie arXiv 2608.01347):** Staffelung nach
Aufgabe ist Standard; **mehr Denktiefe ist nicht immer besser** (xhigh schnitt in der Studie bei Sonnet und
Opus schlechter ab als high); „Opus low" kann „Sonnet high" schlagen; Haiku/Luna gehören *unter* die
Bau-Stufen (Suchen, mechanische Edits); neue Modelle ersetzen eine Stufe nach der Regel **„das günstigste
Modell, das die Stufe im Praxistest löst"**, nicht nach Namen. Vorschlag (wird dir vor Welle 1 vorgelegt):

**Deine Entscheidung dazu (2026-09-27), gilt statt der Recherche-Tabelle:**
- **Zwei getrennte Achsen:** der PM wählt **Modellklasse** und **Denktiefe** je Auftrag getrennt, jeweils
  mit Begründung. Damit die Begründung prüfbar bleibt (DEC-0092 (1) verwarf freien Begründungstext), ist
  sie eine **Auswahl aus einer festen Liste** (z. B. „mechanisch mit Test", „mehrere Dateien",
  „unklarer Fehler", „Architektur", „Nacharbeit nach Fehlschlag"), die ein Hook beim Start erzwingt.
- **Namen (Vorschlag):** Modellklassen **Kilo · Mega · Giga** (Tera frei für eine künftige Spitze);
  Denktiefe mit den Herstellerbegriffen **niedrig · mittel · hoch · sehr hoch**. Heute: Kilo = Sonnet 5 /
  GPT-6 Luna, Mega = Opus 5.5 / GPT-6 Sol, Giga = auf Claude derzeit Opus 5.5 (Fable gedeckelt,
  DEC-0114/0118) / GPT-6 Astra.
- **Haiku: nie zum Coden, nicht in der Leiter** (halluziniert selbst bei Recherchen; schon DEC-0076
  „keine Haiku-Sprosse").
- **Neue Modelle (bald Sonnet 5.5, Haiku 5.5):** Die Watcher melden jedes neue Modell mit einer
  Pflichtfrage: ersetzt es eines der Leiter-Modelle? Entschieden wird nur mit **Beleg**: ein Messlauf auf
  festen Beispielaufgaben dieses Repos (Lösungsquote, Tokens, Kosten je gelöster Aufgabe) gegen das
  bisherige Modell; ohne Messung kein Tausch.
- **Immer aktuell gebrieft:** eine kurze Datei „Welches Modell und welche Denktiefe wofür" mit Quellen
  und Messwerten, von den Watchern aktuell gehalten, steht in jeder Sitzungsübersicht des PM.
- **Technik:** Denktiefe lässt sich pro Start nicht setzen (H169) → der Kit-Generator erzeugt je Rolle
  die Varianten (Modellklasse × Denktiefe) als Rollendateien; der PM wählt eine davon.

Eskalation in einer Zeile: nach zwei gescheiterten Prüfungen derselben Aufgabe Modellklasse oder
Denktiefe eine Stufe hoch **oder** enger schneiden – nie stillschweigend wiederholen. Die hart erlernten
Regeln bleiben: Kilo nur mit Test-Abnahme (DEC-0097/0112), Nacharbeit nicht auf der Spitze
(DEC-0063 (3)), mechanische Fehlschläge steigen nicht (DEC-0107), Prüfer bleibt Mega. Recherche-Befund
bleibt Leitplanke: „sehr hoch" nur für benannte Architektur-Schritte, weil mehr Denktiefe nicht immer
besser ist.

### Welle 1 (4 Ströme parallel, eigene Arbeitskopien, gemeinsame Naht vorab festgelegt)
- **Strom A – Freigaben & Abnahme:** Abnahme-Rundgang (DEC-0123) als Kernel-Befehl + PM-Ablauf;
  Freigabe-Arten 15 → ~6; CR-Fluss „habe ich richtig verstanden? → ja → einbauen"; Werkstatt-Löcher
  ohne Nutzerklick. Baut auf Stream A von Order 7 auf.
- **Strom B – Schutzschicht ersetzen:** (1) Kernel-**Schreibprotokoll** neu bauen (`team-kits/kernel/
  state.py`: Pfad + Prüfsumme je Schreibvorgang); (2) Kontrolle bei Stop und vor jedem Commit: jede
  geänderte Zustandsdatei steht im Protokoll, sonst Verweigerung mit Namen; (3) Nachkontrolle Freigaben
  (APR ↔ echte Antwort in der Mitschrift); (4) erst dann **nur das Schreibziel-Raten** in Shell-Zeilen
  zurückbauen (`gate_write_scope.py`, `.claude/hooks/_harness.py`, betroffene Teile von `_compat.py`);
  Write/Edit-Pfadprüfung, Git-/Push-/Docker-/Testlauf-Erkennung bleiben; (5) `permissions.deny` in einer
  Pilotkopie messen (Windows, bypass, Codex) und nur zusätzlich einsetzen. Vorab: die gespeicherten
  Angriffszeilen + 50 typische Lesebefehle als Messliste.
- **Strom C – PM-Intelligenz & Effizienz:** zwei Achsen Modellklasse (Kilo/Mega/Giga) × Denktiefe mit
  Begründung aus fester Liste (Hook), Rollenvarianten aus dem Generator, „Modell-wofür"-Datei im Brief,
  Watcher-Pflichtfrage + Messlauf bei neuen Modellen; einfache Eskalation; **Lebenszeichen statt
  Polling** (Herzschlag je langem Lauf, Frist, Meldung bei Ausbleiben – für Testläufe, Unteragenten,
  Hintergrundbefehle); **Watcher breiter** (zwei Teile je Bericht, zweiter Blick, Modell-Datei); Blöcke statt Häppchen (Kernel-Hinweis bei überlappenden Dateien, CR in den
  laufenden Block); parallele Bauer als Standard, wenn `check-scopes` disjunkt misst; Polling-Regel;
  Board-Sicht „geliefert / in Arbeit / wartet auf dich / Verbrauch".
- **Strom D – Frontend-Prüfung:** synaipse-Werkzeug (PR-0031/0032) ins Dev-Kit übernehmen, Sperre
  „keine Design-Freigabe bei offenen Kommentaren".

### Welle 2 (2 Ströme parallel, nach Welle 1, weil sie deren Texte/Tests brauchen)
- **Strom E – Textdiät:** erst messen, was beim Start wirklich geladen wird; dann Verfassung + PM-Skill
  deutlich kürzen, oben die Regeln, die das Feld gebrochen hat; Historie/DEC-Nummern in eine nicht
  geladene Nachschlagedatei; die Abschnitts-Pins als **Prüfliste** für den Prüfer (jeder Abschnitt:
  behalten / verschoben / gestrichen mit Grund), danach löschen; am Ende **feste Größengrenzen** für
  Verfassung, Rollendatei und jeden Rollen-Skill, anhebbar nur durch dich per DEC; Satz-Präsenz-Tests
  weg, Verweisprüfung bleibt.
- **Strom F – Tests & Werkstatt:** schneller Kern < 10 min; Gesamtlauf nach jeder Zusammenführung vor dem
  Commit und in CI; Prosa-Tests weg; Werkstatt-Gates dieses Repos nur dort zurück, wo §5 Bremsen misst;
  DEC-Ablöse-Liste + neue DEC zu Werkstatt-Löchern ohne Klick.

### Abschluss
Zusammenführung → ein Prüfer → ein Stempel → Gesamtlauf → Commit, Push, Verteilung →
synaipse-Update + Feldcheck (§5) → dein Abnahme-Rundgang über die Ziele dieser Runde.

---

## 5. Laufend prüfen, was hilft und was bremst (hier und in synaipse)

Nach jeder Welle dieselben Zahlen, vorher/nachher:
| Kennzahl | Ziel |
|---|---|
| Fehlblockaden (Verweigerung eines harmlosen Befehls) je Sitzung | → nahe 0 |
| Freigabe-Klicks je Ziel | ~26 → 3–5 |
| Prüfrunden je Auftrag | ~3 → ≤ 2 |
| Tokens je geliefertem Wunsch | −50 % |
| Anteil Polling-Züge | → 0 |
| Unbemerkt hängende Läufe (kein Lebenszeichen, niemand merkt es) | → 0, Erkennung innerhalb der Frist |
| Aufträge je Ziel / parallele Bauer | wenige große / ≥ 2 wo disjunkt |
| Gesamtlauf-Dauer / schneller Kern | < 10 min Kern |
Jede Regel, die in §5 nur bremst und nichts fängt, wird im nächsten Schritt gestrichen – mit Protokoll.

## 6. synaipse
- Neues Kit (Order 7 + diese Runde) per Sitzungsneustart; danach Feldcheck mit §5-Zahlen.
- Offene Kleinaufträge in große Blöcke je Ziel neu schneiden; Titel-Präfixe P0–P12 beim Rundgang.

## 7. Kritische Dateien
`team-kits/kernel/approvals.py`, `dispatch.py`, `cli.py`, `report.py`, `board.py`;
`team-kits/*/hooks/gate_write_scope.py`, `_compat.py`, `gate_dispatch.py`, `gate_approval.py`;
`.claude/hooks/_harness.py`, `gate_lead_write_scope.py` (Nutzer-Patch);
`team-kits/*/ladder.yaml`, `team-kits/model_tiers.yaml`;
`team-kits/*/constitution/AGENTS.md`, `team-kits/*/skills/project-manager/SKILL.md`;
`tools/test_surface.json`, `.github/workflows/*`; synaipse PR-0031/0032-Werkzeug.

## 8. Verifikation
- Je Strom: Tests, die ohne die Änderung rot sind; Prüfer am Ende des Stroms (nicht je Häppchen).
- Strom B zusätzlich: gespeicherte Angriffszeilen werden spätestens bei der Kontrolle danach erkannt;
  eine Liste von 50 typischen Lesebefehlen läuft ohne Verweigerung.
- Gesamt: Gesamtlauf grün nach dem Merge; §5-Zahlen vorher/nachher in
  `project_memory/staging/FR-0089/metrics-*.md`; Feldcheck in synaipse.

## 9. Grobe Dauer (bei heutigem Nutzungslimit)
Welle 0: ½–1 Tag · Welle 1: 1–2 Tage (4 parallel) · Welle 2: ½–1 Tag · Abschluss: ½ Tag
→ **etwa 3–5 Tage**, danach nur noch Feinschliff nach den §5-Zahlen.
