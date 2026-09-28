# Unabhängige Begutachtung des Harness (FR-0089) — Stand 2026-09-27

Gutachter: ein außenstehender Prüfer (Opus). Er hat nichts davon gebaut, hat nur gelesen und
nichts verändert außer dieser Datei. Jede Zahl unten ist gemessen (Datei und Stelle genannt) oder
ausdrücklich als Schätzung markiert, zusammen mit dem Weg, auf dem man sie messen würde.

---

## 0. Kurz vorweg: was ich selbst beim Messen erlebt habe

Ich habe in diesem Repo nur **gelesen**. Trotzdem haben die Schutzregeln dieses Repos (Gate 1,
`.claude/hooks/gate_lead_write_scope.py`) **vier meiner reinen Lesebefehle verweigert**:

| Befehl (nur lesend) | Was das Gate daraus las |
|---|---|
| `for d in project_memory/*/active; do ... ls ...` | „schreibt in `project_memory/*/active`" |
| `cd .../project_memory && ls; for t in decisions ...` | „schreibt in `project_memory\for`" (das Schleifenwort `for` als Dateiname) |
| PowerShell `... | ForEach-Object { ... }` | „ein Wort mit `{` ist nicht platzierbar" |
| `python -c "... print(s[:330]) ..."` | „ein Wort mit `[` ist nicht platzierbar" |

Das ist kein Randfall, sondern ein Blick direkt auf die teuerste Stelle des Systems (Abschnitt 3,
Punkt 1): Programme, die versuchen, jede Shell-Befehlszeile zu verstehen, bevor sie läuft.

---

## 1. Gesamturteil in fünf Sätzen

1. Im Kern ist das System richtig gedacht, und Teile davon sind hervorragend: ein Projektgedächtnis,
   das nur ein einziges Programm (der „Kernel") beschreiben darf, Freigaben, die nur durch die echte
   Antwort des Nutzers entstehen, und ein getrennter Prüfer, der in fast jeder ersten Prüfrunde echte,
   teils gefährliche Fehler findet.
2. Um diesen Kern herum ist aber ein Apparat gewachsen, der „größer ist als das Haus" (Nutzerwort,
   `DEC-0056`): rund 86.000 Zeilen Python-Produktcode, rund 102.000 Zeilen Tests (5.188 Testfälle,
   Gesamtlauf 64–134 Minuten), 223 nummerierte Löcher, 122 Entscheidungen, über 40 Kit-Versionen in
   16 Tagen.
3. Der größte Teil der Arbeit und der Tokens der letzten Wochen floss in das System selbst: das Ziel
   `PR-0012` „Bug-Null" kostete nach den Zahlen im Rundenlog rund 17–18 Millionen Agenten-Tokens,
   überwiegend für Löcher, die die eigenen Prüfer im eigenen Schutzapparat gefunden hatten — und knapp
   ein Viertel aller Löcher liegt in der Befehlszeilen-Auslegung, die grundsätzlich nie vollständig
   werden kann.
4. Im echten Projekt (synaipse-unified) zeigt sich die Kehrseite: 26 Freigaben in 36 Stunden, 114
   feingeschnittene Aufträge (67 davon warten), 53 von 87 Commits sind reine Buchführung, und 12 der 22
   Lückenmeldungen sind Sackgassen, in denen ein legitimer Schritt verweigert wird und es keine Tür gibt.
5. Mein Urteil: den Wahrheitskern behalten und schützen (Kernel als einziger Schreiber,
   Freigabe-durch-Antwort, Bauer/Prüfer mit rot-zuerst), und in einer Vereinfachungsrunde die
   Befehlszeilen-Auslegung, die Modell-Leiter, die Vielzahl der Freigabe-Arten und die überlangen
   Regeltexte radikal zurückschneiden — das spart nach meiner Schätzung deutlich mehr als die Hälfte
   des laufenden Aufwands, ohne eine einzige echte Garantie aufzugeben.

---

## 2. Die Bestandteile im Einzelnen

Legende: **BEHALTEN** / **VEREINFACHEN** / **ENTFERNEN** / **ERSETZEN DURCH …**

| Bestandteil | Was er liefert (Beleg) | Was er kostet (Beleg) | Urteil |
|---|---|---|---|
| **Freigaben (Approvals)** | Echter Schutz gegen „der Agent genehmigt sich selbst": alle 26 Freigaben in synaipse tragen `minted_via: user_answer_via_approval_hook` (`synaipse-unified/project_memory/approvals/APR-0001..0026.yaml`). Die Stapel-Regel „ein Test muss den Fehler nennen" (`DEC-0100`) hat zwei falsche VERIFIED verhindert (BUG-0044/0050, Rundenlog 2026-09-11 18:43). | 15 Freigabe-Arten (`team-kits/kernel/approvals.py:82`), `approvals.py` allein 4.123 Zeilen. Feld: 26 Freigaben in ~36 h, 18 davon „scope" je Einzelposten, 9 innerhalb von 3½ Minuten (APR-0004..0012, 21:02–21:05). Nutzer: „Reizüberflutung" (`DEC-0119`). Dieses Repo: 80 aktive APR. | **BEHALTEN** (die Garantie) + **VEREINFACHEN** (Anzahl): genau das, was `DEC-0119`/`DEC-0123` beschließen, aber noch nicht gebaut ist — Plan-Karte, gesammelte Verständnis-Karte, Abnahme-Rundgang am Ende, plus Unumkehrbares (Push, Geld, Löschen). Arten von 15 auf ~6. |
| **Projektgedächtnis / Kernel** | Zustand überlebt jede Sitzung; der PM startet mit Masterplan und Items statt bei Null; Index und Sitzungsübersicht werden erzeugt statt von Hand gepflegt. Das Gate, das Handschreiben verbietet, ist gemessen begründet: ein handgeschriebenes `EVD` mit `result: pass` öffnete früher den Commit (CLAUDE.md, „Der Zustand dieses Projekts"). V1→V2-Migration in synaipse ist gelaufen. | Kernel 35.454 Zeilen in 31 Dateien (`report.py` 5.065, `dispatch.py` 4.710, `approvals.py` 4.123, `migrate.py` 3.242). 509 EVD-Dateien in diesem Repo — jeder Testlauf ist ein Item. Lease/TTL-Mechanik erzeugt Feld-Sackgassen (Lückenmeldungen 7, 13, 14: abgelaufene Lease, Aufgabe hängt in LEASED/IN_PROGRESS, kein Ausweg). 53 von 87 synaipse-Commits seit 25.09. sind `chore(memory)`. | **BEHALTEN** (einziger Schreiber, typisierte Items, erzeugter Index) + **VEREINFACHEN**: Lease-Zustände entschärfen (abgelaufene Lease = automatisch zurück, nie Sackgasse), Buchungs-Commits bündeln, Berichts-/Dispatch-Code halbieren. |
| **Hooks: Invarianten-Gates** (Freigabe prägen, Commit/Merge nur mit Beweis, Spawn nur mit Auftrag, kein Push ohne Nutzer) | Fangen echte Fehler: der Prüfer fand `git push origin HEAD:main` ohne Abnahmebeweis (TSK-0139 F1, Rundenlog 22:11) — das Gate wurde repariert. Commit-Gate verhindert „fertig" ohne Testlauf. | Überschaubar: das sind die kleinen Gates (`gate_spawn_needs_item.py` 82 Zeilen, `gate_commit_evidence.py` 435). | **BEHALTEN**. |
| **Hooks: Befehlszeilen-Auslegung** (`gate_write_scope.py` 2.297 Z., `_compat.py` 2.431 Z., `.claude/hooks/_harness.py` 2.938 Z., Teile von `gate_shell_hygiene`, `gate_git`, `gate_test_scope`) | Verhindert, dass ein Agent aus Versehen per Shell in Zustand/Schutzbereich schreibt. Einige echte Fälle (H3, H5). | Knapp ein Viertel der 213 Löcher im Index (`docs/POST_V2_WISHLIST.md` §12; meine Zählung ~50: Heredoc, Umleitung, Ersetzung, Tilde, Präfixwort, `exec -a`, `sudo -u` …). Viele Löcher sind „Preis des Fixes" eines anderen (H11, H15, H57 im Titel). Unschließbarer Rest benannt (H11: ein selbstgeschriebenes Skript schreibt trotzdem, `DEC-0056`). Über-Verweigerung: meine 4 Lesebefehle (Abschnitt 0), H18/H19/H20/H64/H68/H188/H220, im Feld 12 Sackgassen (Abschnitt 5). Runden 3b/4/5 haben dennoch weiter gegen den Agenten selbst gehärtet (H204, H205, H214, H219) — gegen `DEC-0056` (a). | **ERSETZEN DURCH** Werkzeug-Regeln (Write/Edit-Verbot per Berechtigung) + Erkennung **danach** (Prüfsumme/Audit beim Stop und vor dem Commit). Siehe Abschnitt 3, Punkt 1. |
| **Agenten / Rollen** | Klare Rollen (9 im dev-Kit), Presets `solo/duo/team` (`team-kits/dev-team/presets.yaml`), „leichte Form": ein Bauer pro Ziel (`DEC-0087`) — gemessen günstiger als die Generationen davor. Parallele Ströme nach Dateibesitz halbieren die Wartezeit (`DEC-0102`: 5 h 22 statt ~10,4 h). | Im Feld wird die leichte Form nicht befolgt: der synaipse-PM legte 96 Aufträge in 9 Minuten an und arbeitet sie strikt seriell ab, mit eigenem Bau- **und** QA-Auftrag je kleiner Änderung (Rundenlog 2026-09-26 21:34). 114 aktive TSK, davon 67 READY, 26 QA-Aufträge. | **BEHALTEN** + **VEREINFACHEN**: die Regel „ein Bauer pro Ziel" muss **Mechanik** sein (z. B. Kernel verweigert den zweiten offenen Bauauftrag unter einem kleinen Ziel), nicht Satz 7 in 54 KB Text. |
| **Modell-Leiter** (Sprosse, Aufwand, Eskalation, Standard vs. Boden, Anbieter-Deckel) | Ergebnis nach 1½ Monaten: „Opus für alles, Architektur auf Opus xhigh, Sonnet nur mit Test" (`DEC-0095`, `DEC-0097`, `DEC-0118`). Das ist vernünftig. | Rund 17 Entscheidungen nur zu Modellstufen (u. a. DEC-0034, 0053, 0055, 0075–0078, 0081, 0088, 0091, 0092, 0095–0097, 0105, 0107, 0112, 0114, 0118). Die Aufwand-Achse wird berechnet, aber **nie angewendet** — das Agent-Werkzeug kennt keinen Aufwand pro Spawn (H169, ACCEPTED_EXCEPTION). Auf Codex gibt es gar keinen Halt am Spawn (H173). TSK-0151 kostete ~1,73 Mio. Tokens, 3 Prüfrunden, 4 Nacharbeiten fast nur hierfür (`DEC-0116`). Feld: der Architekt war blockiert, weil die Leiter Fable erzwang und Fables Filter den Start verweigerte (Lückenmeldung 2). | **ERSETZEN DURCH** feste `model:`-Angabe je Rolle in der Rollendatei + **eine** Regel: nach zwei gescheiterten Prüfungen desselben Auftrags fragt der PM den Nutzer oder hebt die Stufe. Leiter-Code, Checkpoint-Zeilen, Test-Form-Leser, `by_provider`-Buchführung entfernen. |
| **Skills / Verfassungstexte** | Enthalten viel echte, teuer gelernte Erfahrung („Regeln, die echte Läufe gebrochen haben"). Die Sprache-an-den-Nutzer-Regeln (einfaches Deutsch) sind gut. | Verfassung `AGENTS.md` 52.045 Byte, längste Zeile 2.084 Zeichen, 46 DEC-Verweise; PM-Skill 54.616 Byte, 42 DEC-Verweise; PM-Rollendatei 10.673 Byte → **~117 KB ≈ 30.000 Tokens** Pflichtlektüre bei jedem PM-Start (Schätzung: Zeichen/4). Viel Text beschreibt, was **nicht** durchgesetzt wird (z. B. AGENTS.md §2 Punkt 2 und 9). Befund im Feld: die wichtigste Regel (Zielgröße der Aufträge) wird nicht befolgt. | **VEREINFACHEN**: Verfassung + PM-Skill auf zusammen ≤ 30 KB; Entstehungsgeschichte, DEC-Nummern und „was nicht erzwungen wird" in eine Nachschlagedatei, die nicht geladen wird. |
| **Handwerksgedächtnis je Rolle** | Inhaltlich das Wertvollste im Feld: synaipse `frontend-developer` hat 104 konkrete, wiederverwendbare Lektionen (z. B. „Vite legt kleine Dateien als `data:` ein, das bricht die strenge CSP", „jsdom löst `var()` nicht auf") — `synaipse-unified/.claude/agent-memory/frontend-developer/MEMORY.md`. | Die Mechanik blockiert sich selbst: Budget 20 Themen, vorhanden 103 → `guard_memory_budget` verweigert **jede** Bearbeitung, also kann niemand es je wieder aufräumen (Lückenmeldung 21). Gleichzeitig ging ein Schreiben per Shell ungesehen durch (Lückenmeldung 20). | **BEHALTEN** (Inhalt) + **VEREINFACHEN** (Budget nur als Warnung + eine Aufräum-Tür, keine Verweigerung). |
| **Prüfschleifen** (Bauer/Prüfer, rot-zuerst, Mutationen) | Der stärkste Qualitätshebel. Erste Prüfrunde scheitert praktisch immer (Gen 6: „first-round FAIL rate 3/3"; `DEC-0102`: 10 Runden für 3 Ströme). Gefundene echte Fehler: Push-Umgehung (TSK-0139 F1), Stapel-Freigabe verifizierte einen Fehler mit nicht existierendem Test (F2), Eskalation, die de-eskaliert (TSK-0136 F1), Heredoc über Pipe schreibt Zustand (TSK-0142 B1), Archiv-Tür per Verzeichnis-Verknüpfung nach außen (TSK-0152 F4). Die Recherche zu FR-0091 bestätigt: auch das stärkste Modell behauptet falsche Testergebnisse → Prüfer bleibt. | Im Schnitt ~3 Prüfrunden pro Auftrag, jede 8–99 Minuten und 25–318 k Tokens. Ein großer Teil der Befunde betrifft **Text** (Zahlen in Kommentaren, „Docstring behauptet mehr als gebaut", P-Zeilen) — `DEC-0111` (7) macht sogar jede Zahl in Prosa zum Befund. Der Gesamtlauf fand in 3 von 3 Aufträgen nichts, was der Prüfer übersehen hätte (`DEC-0121`). | **BEHALTEN** (Trennung, rot-zuerst) + **VEREINFACHEN**: nur Verhaltensbefunde lösen eine Nacharbeit aus; Textbefunde werden gesammelt und einmal am Ende erledigt. Gesamtlauf nur nach dem PASS (bereits `DEC-0121`). |
| **Wächter / Radar** (`claude-watcher`, `codex-watcher`) | Liefert gelegentlich echten Nutzen: der Bericht vom 25.09. meldete „Opus 5.5 ist GA und neuer Standard" → führte zu `DEC-0114` (`radar/2026-09-25-claude-by-claude.md`). | Zwei Agentenläufe pro Woche, zwei Berichte à ~35 KB, eigene Planungs-Entscheidungen (DEC-0085, 0089, 0090, 0098), eigenes Werkzeug `tools/radar_routine.py` (903 Z.), Zeitplan in der Desktop-App, die das Repo nicht sehen kann (H186). | **VEREINFACHEN**: ein Wächter, monatlich statt wöchentlich, Bericht ≤ 1 Seite mit höchstens 3 Empfehlungen. |
| **Meta-Harness dieses Repos** (eigene Gates, Nutzer-Patches, Löcher-Buchhaltung) | Hat das Produkt geschützt, während drei Rollen daran arbeiteten; die Löcherliste ist ehrlich und vollständig geführt. | `.claude/hooks` 4.720 Z. Produktcode + 8.459 Z. Gate-Tests (~550 Tests, 12–20 Min.). Der Lead darf die eigenen Gates nicht reparieren → **drei Nutzer-Patches**, die der Nutzer außerhalb von Claude Code fahren musste (Rundenlog 25.09. 14:47, 26.09. 08:00, 21:34), ein vierter wartet. 223 Löcher, 163 Einzel-Dokumente unter `docs/holes/`, ein generierter Zeigerindex, über 40 Versionsstempel in 16 Tagen. Die meisten Löcher fand das System in sich selbst — es ist sein eigener größter Kunde. | **VEREINFACHEN**: in der Werkstatt reichen git, CI, Bauer/Prüfer und ein einziges Gate (kein Werkzeug-Schreiben in `project_memory/`). Löcher als normale Fehlerliste; Einzeldokumente abschaffen. |
| **Mehranbieter-Erzeugung** (Claude + Codex) | Kits laufen auch unter Codex; synaipse nutzt es tatsächlich (Commit „record user-selected gpt-6-astra"). Offene Anbieter-Zukunft (`DEC-0115`, FR-0023) ist dem Nutzer wichtig. | `gen_provider_artifacts.py` 1.445 Z., eine Paritätsmatrix, Leiter je Anbieter, Buchführung je Anbieter (H221), Codex kann den Spawn gar nicht halten (H173). Jede Kit-Änderung muss für zwei Anbieter gedacht und getestet werden. | **VEREINFACHEN**: Claude ist die Referenz; Codex bekommt erzeugte Dateien „nach bestem Vermögen", ohne Paritätsversprechen und ohne eigene Stufen-Buchführung. |
| **Fehler-/Ausnahme-Klick-Ablauf** (Stapel-Verifikation, `hole_exception`) | Macht den Abschluss vieler Fehler nachvollziehbar; hat eine echte Kontrolle („nennt ein Test den Fehler?"). | Weit über 50 Nutzer-Klicks nur für `PR-0012`; 71 Löcher per Klick als „akzeptierte Ausnahme" geschlossen. Die erste Ausnahme-Frage lehnte der Nutzer ab: „Wieso wird das nicht behoben? … will nicht blind Freigabe erteilen" (Rundenlog 2026-09-12 09:23). Der Nutzer unterschreibt Dinge über die innere Werkstatt, die er nicht beurteilen kann. | **ERSETZEN DURCH** den Abnahme-Rundgang am Ende (`DEC-0123`) für **Produkt**-Fehler; Werkstatt-Löcher entscheidet der Lead mit Protokoll, ohne Nutzerklick. |

---

## 3. Die fünf größten Überbauten — und was stattdessen die echte Garantie hält

### 1. Die Shell-Befehlszeile verstehen wollen

**Was heute passiert:** Vor jedem Shell-Befehl laufen mehrere Python-Programme, die die Zeile wie
eine Shell zerlegen (Anführungszeichen, Umleitungen, Heredocs, Variablen, Präfixwörter, `cd`-Folgen,
PowerShell-Klammern) und raten, ob irgendwo in einen geschützten Bereich geschrieben wird.
**Warum das Überbau ist:** Das ist ein Wettlauf, der nicht zu gewinnen ist — das System hat es selbst
gemessen und entschieden (H11 unschließbar, `DEC-0056`). Trotzdem liefen danach noch ganze Runden gegen
genau diese Klasse (H204, H205, H214, H219, BUG-0304 mit `exec -a`, `sudo -u`, `nice -n`). Und die
Auslegung verweigert gleichzeitig harmlose Befehle (4 meiner Lesebefehle; H188: ein `grep` wird als
„schreibt auf C:\" gelesen; im Feld 12 Sackgassen).
**Die echte Garantie:** „Der Projektzustand wird nur vom Kernel geschrieben, und ein verfälschter
Zustand kommt nicht in einen Commit."
**Einfacherer Ersatz, der sie hält:**
- Werkzeug-Ebene: `Write`/`Edit`/`NotebookEdit` auf `project_memory/**` und `.claude/**` per
  Berechtigungsregel verbieten (das ist exakt, weil der Pfad ein Feld ist, keine Zeile).
- Erkennung danach statt Raten vorher: der Kernel führt bereits ein Audit seiner Schreibvorgänge;
  beim Sitzungs-Stop und vor jedem Commit vergleicht ein kleines Gate „geänderte Zustandsdateien" gegen
  „Kernel-Audit". Stimmt es nicht, wird der Commit verweigert und die Datei aus git
  wiederhergestellt. Der Schutz-Bündel-Hash (`kit_trust_state`) tut das Gleiche schon für `.claude/`.
- Für die Shell bleibt höchstens eine **dumme** Regel: eine Zeile, die einen geschützten Pfad
  wörtlich nennt und ein offensichtliches Schreibverb trägt, wird mit freundlichem Hinweis abgelehnt —
  ohne Vollständigkeitsanspruch.
**Erwarteter Effekt:** grob 5.000–7.000 Zeilen weniger, eine ganze Lochklasse (~50 Löcher) erledigt
sich als Klasse, keine Über-Verweigerungen mehr bei Lesebefehlen.
**Unsicher, und so misst man es:** ob Claude Code auf Windows eine echte Datei-Sandbox für Bash
bietet, habe ich nicht geprüft. Das entscheidet nichts Grundsätzliches (die Erkennung danach wirkt
immer), aber es bestimmt, ob man zusätzlich vorher sperren kann. Messung: in einer Pilotkopie die
Berechtigungsregeln setzen und die gespeicherten Angriffszeilen der Löcher H11/H16/H204/H214 fahren —
wird jede Verfälschung spätestens am Commit erkannt?

### 2. Leser, die natürliche Sprache beurteilen, und Tests, die Prosa durchsuchen

**Was heute passiert:** Programme entscheiden über Wortlisten, ob ein Satz eine Verneinung ist, ob
ein Abnahmekriterium „ein Test" ist, ob eine Datei eine Preisangabe enthält, ob ein Kommentar mehr
behauptet als gebaut ist. Jede Runde findet ein neues Wort (`niemals`, `nothing`, `weder…noch`, der
mehrdeutige Genitiv — H194, H212, `DEC-0102` (3): „ein Wortinventar über eine Sprache wird nie fertig").
**Das System hat es teilweise schon erkannt:** `DEC-0112` (Verneinungsleser entfernt), `DEC-0116`
(Freitext-Eigenschaften sind ein Schnittfehler). Aber es gibt noch viele solcher Leser (H141, H157,
H159, H189–H191, H195, H216, H217) und die Hausregel „keine Zahl in Prosa" (`DEC-0111` (7)) erzeugt
laufend neue Prüfbefunde.
**Die echte Garantie:** „Was die Dokumentation über Schutz behauptet, stimmt."
**Einfacherer Ersatz:** Dokumentation beschreibt nur noch **was** und **warum**, nie „wie vollständig";
Eigenschaften stehen ausschließlich in Tests, und der Text verweist auf den Testnamen (das tut die
Regel `SR-0008` im Prinzip schon). Prosa-Genauigkeit ist Sache einer einmaligen Lese-Durchsicht am
Ende, nicht eines Tests und keiner Nacharbeitsschleife.
**Erwarteter Effekt:** nach Schätzung ein Drittel weniger Prüfrunden (in `DEC-0116` allein zwei
Runden ≈ 700 k Tokens nur durch zwei Prosa-Leser).

### 3. Die Modell-Leiter

**Was heute passiert:** Der Kernel leitet für jeden Auftrag Sprosse und Aufwand ab, zählt
Fehlschläge, hebt erst den Aufwand, dann die Sprosse, kennt Standard und Boden, Anbieter-Deckel,
Test-Form-Leser, Verteilungsstatistik und druckt eine Reflexions-Checkliste vor jedem Bau.
**Warum das Überbau ist:** Das Ergebnis ist praktisch konstant („Opus, Architektur Opus xhigh") und
der Aufwand wird auf Claude **gar nicht angewendet** (H169). Rund 17 Entscheidungen, mehrere
Millionen Tokens (TSK-0135, 0136, 0137, 0151) und eine Feld-Blockade (der Architekt kam nicht an Fables
Filter vorbei, Lückenmeldung 2).
**Die echte Garantie:** „Teure Modelle nur, wo sie sich lohnen; nach wiederholtem Scheitern wird
eskaliert, nicht endlos wiederholt."
**Einfacherer Ersatz:** feste `model:`/`effort:` je Rollendatei (Opus; eine billige Rolle für
Mechanisches), und **eine** Zeile Regel: „Nach zwei gescheiterten Prüfungen desselben Auftrags:
Auftrag neu schneiden oder den Nutzer fragen." Die Zählung, wie oft geprüft wurde, liefert der Kernel
ohnehin aus den EVD-Items.
**Erwarteter Effekt:** ein ganzer Kernel-Bereich (Leiter-Ableitung in `dispatch.py`, Teile von
`report.py`), `ladder.yaml` × 3, Teile von `model_tiers.yaml` und ~600 Z. `test_model_ladder.py`
entfallen; keine Spawn-Verweigerungen wegen Modellnamen mehr.

### 4. Zu viele Freigabe-Arten und zu viele Klicks

**Was heute passiert:** 15 Freigabe-Arten; im Feld eine Freigabe je Änderungswunsch, je Fehler, je
Lieferung; in diesem Repo Stapel-Klicks für Werkstatt-Löcher.
**Die echte Garantie** (und die ist hervorragend, siehe Abschnitt 4): „Kein Agent kann sich selbst
genehmigen — nur die Antwort des Nutzers erzeugt eine Freigabe."
**Einfacherer Ersatz:** der schon beschlossene Ablauf aus `DEC-0119`/`DEC-0123`, konsequent: drei
Momente je Ziel (Plan, gesammelte Verständnis-Karte, Abnahme-Rundgang am Ende) + Unumkehrbares
(Push, Kit-Update, Geldbeträge, Löschungen). Fehler brauchen keine Freigabe. Die Prägung durch die
Antwort bleibt exakt wie sie ist.
**Erwarteter Effekt:** im Feld von ~26 Klicks in 36 h auf ~3–5 pro Ziel; die Klicks, die bleiben,
sind solche, die der Nutzer auch verstehen kann.

### 5. Die Werkstatt regiert sich so streng wie das Produkt

**Was heute passiert:** Dieses Repo hat eigene Gates, die den eigenen Lead daran hindern, die eigenen
Gates zu reparieren; Reparaturen gehen als Patch-Skript zum Nutzer, der sie außerhalb von Claude Code
fährt. Jede Lücke wird ein nummeriertes Loch mit eigenem Dokument, Status-Automat, Ausnahme-Klick und
generiertem Index. Jede Runde endet in einer Retrospektiv-Entscheidung, die neue Regeln hinzufügt
(`DEC-0102`: 5 Regeln, `DEC-0111`: → 9 Regeln, `DEC-0116`, `DEC-0121` …) — Regeln werden nur
hinzugefügt, nie entfernt.
**Die echte Garantie:** „Ein Paket ist erst fertig, wenn ein anderer als sein Bauer es gemessen hat,
und nichts wird ohne Beweis committet."
**Einfacherer Ersatz:** git + CI + Bauer/Prüfer + ein Commit-mit-Beweis-Gate + Werkzeug-Schreibverbot
für `project_memory/`. Die Befehlszeilen-Auslegung im Werkstatt-Gate 1 entfällt (Abschnitt 3.1). Löcher
werden normale BUG-Items ohne Einzeldokument und ohne Nutzerklick. Jede Retrospektive darf nur so
viele Regeln hinzufügen, wie sie gleichzeitig streicht.
**Erwarteter Effekt:** keine Nutzer-Patches mehr; der Nutzer wird nur noch zum Produkt gefragt.

---

## 4. Die fünf Dinge, die wirklich sehr gut sind — und bei jeder Vereinfachung geschützt werden müssen

1. **Freigabe entsteht nur durch die echte Antwort des Nutzers.** Der Haken liest die Antwort auf die
   Frage und prägt erst dann (`gate_approval.py`, `minted_via: user_answer_via_approval_hook` in allen
   26 synaipse-Freigaben). Das ist die eine Stelle, an der ein Agent sich sonst selbst „erlauben"
   könnte, was er will. Nie aufweichen, auch nicht durch „der Nutzer hat im Chat ja gesagt".
2. **Der Kernel als einziger Schreiber des Projektzustands, mit typisierten Items und erzeugten
   Übersichten.** Das ist das Langzeitgedächtnis, das der Nutzer bezahlt: jede Entscheidung, jede
   Freigabe, jeder Beweis ist nach Wochen noch auffindbar (Beispiel: dieser Bericht konnte jede Runde
   seit dem 11.09. mit Uhrzeit, Kosten und Befund nachvollziehen). Die Garantie ist gemessen begründet
   (ein handgeschriebenes Beweis-Item öffnete früher den Commit).
3. **Bauer und Prüfer getrennt, rot-zuerst, Mutationen.** Der Prüfer fand in fast jeder ersten Runde
   echte Fehler, einige davon gefährlich (Push-Umgehung, Freigabe eines nicht existierenden Tests,
   Schreibweg nach außen). Die Regel „jeder Fix braucht einen Test, der ohne ihn rot wird" macht die
   Aussagen des Systems prüfbar. Das ist der Grund, warum man dem Ergebnis trauen kann.
4. **Messen statt raten — und lernen aus den Messungen.** Beispiele mit Wirkung: frische Nacharbeiter
   statt Wiederaufnahme senkten den Kontext pro Schritt um 53–62 % und die Gesamteingabe um bis zu
   37 % (`FR-0093`); parallele Ströme nach Dateibesitz halbierten die Wartezeit (`DEC-0102`); der
   Gesamtlauf nach dem PASS statt davor (`DEC-0121`). Dazu die **Lückenmeldung aus dem Feld**
   (`report-gap` → `kit_gaps.jsonl` → Ernte → 12 neue Fehler-Items): ein echter Rückkanal vom Projekt
   zum Kit.
5. **Das Handwerksgedächtnis der Rollen — der Inhalt.** Die 104 Lektionen der Frontend-Rolle in
   synaipse sind genau das Wissen, das ein Mensch im Team über Monate sammelt. Dazu gehört auch die
   leichte Form „ein Bauer pro Ziel" mit Masterplan-zuerst: das ist die Arbeitsform, die gemessen am
   günstigsten war — sie muss nur befolgt werden.

---

## 5. Was fehlt, das der Nutzer dringender braucht als vieles, was es gibt

1. **Kostenanzeige vorher und eine echte Kostenbremse.** Der Nutzer hat selbst gemerkt, dass 30 %
   seines Wochenkontingents in 8 Stunden weg waren (Rundenlog 2026-09-11 07:07). Eine Regel „ab 50 %
   keine neuen Agenten ohne sein Wort" gibt es nur als Text (`DEC-0095` (6)); drei Aufträge wurden
   vom Nutzungslimit mitten im Lauf getötet (25.09., 26.09., 27.09.). Gebraucht: vor jedem Ziel eine
   Schätzung („etwa X % deines Wochenkontingents"), während der Arbeit eine Anzeige, und ein Stopp, den
   ein Gate hält.
2. **Eine Produkt-Sicht: „Was hat mein Produkt diese Woche gewonnen?"** Heute sieht man Items,
   Stempel, Runden. Im Feld sind 53 von 87 Commits Buchführung und 18 Produkt-Commits
   (feat/fix/test über alle Branches). Gebraucht: eine Seite in einfachem Deutsch — geliefert,
   in Arbeit, wartet auf dich, Kosten — und eine Kennzahl „Anteil Produkt vs. Verwaltung".
3. **Ein stabiler Kit-Kanal.** Über 40 Versionsstempel in 16 Tagen; jedes Update kostet im Feld eine
   Zusammenführungsrunde, oft eine leere (Lückenmeldung 8: die Liste meldet Änderungen, die es nicht
   gibt). Gebraucht: „stabil" (z. B. monatlich) und „Fehlerbehebung" getrennt; Feldprojekte bekommen
   nur „stabil".
4. **Türen statt Sackgassen.** 12 der 22 Feld-Lückenmeldungen sind Situationen, in denen ein
   legitimer Schritt verweigert wird und kein Weg bleibt — sogar dann, wenn der Nutzer im Chat
   ausdrücklich zugestimmt hat (Docker-Aufräumen, Lückenmeldungen 10/11). Gebraucht: eine allgemeine
   „vom Nutzer erlaubte Ausnahme" über **denselben** Prägeweg (Frage → Antwort → einmalige, protokollierte
   Erlaubnis für genau diesen Befehl). Das hält die Garantie aus Abschnitt 4.1 und beendet die Sackgassen.
5. **Ein Ende-zu-Ende-Maß für Qualität am Produkt.** Heute misst das System vor allem sich selbst
   (5.188 Tests, überwiegend über Hooks und Kernel). Gebraucht: ein Beispielprojekt, an dem jede
   Kit-Version einmal „vom Wunsch zur abgenommenen Funktion" läuft, und das Zeit, Tokens und Klicks
   pro geliefertem Wunsch misst. Das ist die Zahl, die der Nutzer eigentlich optimieren will.
6. **Unbeaufsichtigtes Arbeiten.** Gemessen: im Hintergrund-Modus erreicht der PM die Freigabe-Stelle
   gar nicht (Rundenlog 2026-09-11 08:44, `headless_pm_stop_point`). Wer Autonomie will, braucht einen
   Modus „arbeite den freigegebenen Plan über Nacht ab und sammle alle Fragen für morgen".

---

## 6. Vorschlag: eine Vereinfachungsrunde in sechs Schritten

Reihenfolge ist Absicht: erst messen, dann das Teuerste mit dem geringsten Risiko abbauen.

| # | Schritt | Was genau | Erwarteter Effekt | Wie man den Erfolg misst |
|---|---|---|---|---|
| 1 | **Ausgangswerte messen, Kit einfrieren** (½ Tag) | `tools/measure_agent_tokens.py` über TSK-0138…0156 laufen lassen (echte Summe statt meiner Schätzung); in synaipse die letzten 7 Tage zählen: Klicks pro Ziel, Tokens pro geliefertem Wunsch, Anteil Produkt-Commits. Ab jetzt nur noch ein „stabiler" Kit-Stand fürs Feld. | Eine Zahl, an der sich jede weitere Änderung messen lassen muss. | Die drei Kennzahlen stehen in einer Datei unter `staging/FR-0089/`. |
| 2 | **Freigaben nach `DEC-0119`/`DEC-0123` fertig bauen und Arten zusammenlegen** | Plan-Karte, gesammelte Verständnis-Karte, Abnahme-Rundgang, Unumkehrbares; 15 Arten → ~6; keine Freigabe für Fehler; Werkstatt-Löcher ohne Nutzerklick. Dazu die „vom Nutzer erlaubte Ausnahme" über den Prägeweg (Abschnitt 5.4). | Feld: ~26 → ~3–5 Klicks pro Ziel; keine Sackgassen mehr, wo der Nutzer „ja" gesagt hat. | Klicks pro Ziel in synaipse vorher/nachher. |
| 3 | **Befehlszeilen-Auslegung durch Berechtigung + Erkennung danach ersetzen** | Write/Edit-Verbot auf Zustand und `.claude/` per Berechtigungsregel; Stop-/Commit-Prüfung „geänderte Zustandsdateien ⊆ Kernel-Audit"; `gate_write_scope`/`_compat`/`_harness` auf eine dumme Wörtlich-Regel zurückbauen. Vorher in einer Pilotkopie mit den gespeicherten Angriffszeilen prüfen. | ~5–7 k Zeilen weniger; ~50 Löcher als Klasse erledigt; keine verweigerten Lesebefehle; weniger Hook-Wartezeit pro Befehl. | Angriffszeilen der Klasse H11/H16/H204/H214 werden spätestens am Commit erkannt; 0 Verweigerungen auf einer Liste von 50 typischen Lesebefehlen. |
| 4 | **Modell-Leiter durch feste Rollen-Pins + eine Eskalationsregel ersetzen** | Leiter-Ableitung, Checkpoint-Zeilen, Test-Form-Leser, Anbieter-Buchführung entfernen; ein DEC ersetzt die ~17 Stufen-DECs. | Weniger Kernel-Code, keine Spawn-Blockaden wegen Modellnamen, eine Entscheidungsstelle statt siebzehn. | Keine Lückenmeldung „Spawn wegen Modell verweigert" in 2 Wochen Feldbetrieb. |
| 5 | **Textdiät für Verfassung und PM-Skill** | Zusammen ≤ 30 KB (heute ~107 KB + 10,7 KB Rollendatei); oben die zehn Regeln, die das Feld gebrochen hat (zuerst: ein Bauer pro Ziel); alles über Entstehung, DEC-Nummern und „was nicht erzwungen wird" in eine nicht geladene Nachschlagedatei. Die Zielgrößen-Regel zusätzlich als Kernel-Mechanik. | ~20.000 Tokens weniger bei jedem PM-Start; der PM befolgt die wichtigen Regeln eher. | Aufträge pro Ziel in synaipse (heute: 96 Aufträge für eine Handvoll Ziele) vorher/nachher. |
| 6 | **Werkstatt verschlanken und Test-Suite teilen** | Werkstatt-Gate 1 ohne Shell-Auslegung; Loch-Einzeldokumente abschaffen; Prosa-Tests und Parser-Schreibweisen-Tests mit ihren Parsern löschen; Suite in einen schnellen Kern (Ziel < 10 Min.) pro Runde und den vollen Lauf in CI/nachts teilen; Prüfer-Befunde in „Verhalten" (blockiert) und „Text" (einmal gesammelt am Ende) trennen; Retrospektiven nur mit gleichzeitiger Regel-Streichung. | Kürzere Runden, keine Nutzer-Patches mehr, deutlich weniger Tokens pro Auftrag. | Prüfrunden pro Auftrag (heute ~3) und Tokens pro Auftrag vorher/nachher; Laufzeit des schnellen Kerns. |

Grobe Gesamterwartung (Schätzung, nicht gemessen): der laufende Aufwand pro geliefertem
Produktwunsch sinkt um mehr als die Hälfte, weil die drei größten Kostentreiber — Löcher in der
Befehlszeilen-Auslegung, Prosa-Leser, Leiter-Mechanik — zusammen den Großteil der Runden seit dem
11.09. erzeugt haben.

---

## 7. Wo ich unsicher bin — und was es messen würde

| Aussage | Unsicherheit | Messung |
|---|---|---|
| `PR-0012` ≈ 17–18 Mio. Agenten-Tokens | Aus den Einzelzahlen im Rundenlog addiert (TSK-0138 ~0,75 M, 0139 ~1,0 M, 0140 ~1,2 M, 3b ~4,9 M inkl. Zielrunde, Order 4 ~4 M, Order 5 ~1 M, 6a ~1,73 M, 6 ~1,2 M, 7 ≥ 1,5 M); einige Posten fehlen oder sind geschätzt; die eigene Lead-Sitzung ist nicht enthalten. | `tools/measure_agent_tokens.py` über alle Aufträge des Ziels. |
| „etwa zwei bis drei Wochenkontingente" | Leitet sich aus „~1,8 M ≈ 30 % in 8 h" ab (Rundenlog 07:07), damals mit Fable-Anteil, der teurer zählt. Der Nutzer hatte für `PR-0012` ausdrücklich „Tempo vor Budget" gesagt (`DEC-0099`). | Nutzungsanzeige des Kontos über die betreffenden Tage. |
| ~50 von 213 Löchern betreffen Befehlszeilen-Auslegung | Meine Einordnung nach Titeln im Index (`docs/POST_V2_WISHLIST.md` §12), nicht nach Code. | Ein Feld „Klasse" an den Loch-Items und eine Zählung. |
| Hook-Wartezeit pro Shell-Befehl | Gemessen ist nur ein Hook (0,10–0,38 s, Rundenlog 01:27/01:46); bei ~9 Hooks pro Bash-Aufruf vermute ich 1–3 s. | Zeitstempel vor/nach der Hook-Kette in einer Pilotsitzung über 100 Befehle. |
| Datei-Sandbox für Bash unter Windows | Nicht geprüft. Die vorgeschlagene Erkennung danach funktioniert unabhängig davon. | Pilotkopie, siehe Schritt 3. |
| Der PM befolgt kürzere Texte besser | Plausibel, nicht gemessen. | Schritt 5, Aufträge pro Ziel vorher/nachher. |

---

## Anhang: die wichtigsten Messwerte auf einen Blick

| Größe | Wert | Quelle |
|---|---|---|
| Kernel | 35.454 Zeilen, 31 Dateien | `team-kits/kernel/*.py` |
| Hooks dev-Kit | 14.253 Zeilen, 34 Dateien, 64 Registrierungen | `team-kits/dev-team/hooks/`, `settings/settings.json` |
| Hooks research + office | 31.770 Zeilen (großteils Spiegel) | `team-kits/{research,office}-team/hooks/` |
| Werkstatt-Gates | 4.720 Z. Produkt + 8.459 Z. Tests | `.claude/hooks/` |
| Tests | 3.201 Testfunktionen (5.188 Fälle im Gesamtlauf), 101.850 Z. in 52 Testdateien | `tools/test_*.py`, `.claude/hooks/test_gates.py`, Rundenlog |
| Gesamtlauf | 64–134 Min. (4.116 s, 4.574 s, 8.058 s, ~87 Min.) | Rundenlog 09-12 20:10, 09-13 06:51/13:44, 09-26 |
| Verfassung + PM-Skill + PM-Rolle | 52.045 + 54.616 + 10.673 Byte | `team-kits/dev-team/...` |
| Entscheidungen | 119 aktiv + 3 archiviert; ~17 davon nur zu Modellstufen | `project_memory/decisions/active/` |
| Items in diesem Repo | ~325 BUG, ~156 TSK, ~96 FR, 122 DEC, ~509 EVD, 80 APR | Index + Archiv |
| Löcher | 213 im Index: 133 VERIFIED, 74 ACCEPTED_EXCEPTION, 2 REJECTED, 1 DUPLICATE, 1 TRIAGED, 2 OPEN | `docs/POST_V2_WISHLIST.md` §12 |
| Prüfrunden | ~3 pro Auftrag; 10 für 3 Ströme (3b), 10 für Order 4 | `DEC-0102`, `DEC-0111` |
| Kosten-Hebel FR-0093 | Kontext pro Schritt −53 bis −62 %, Eingabe −15 bis −37 % | `FR-0093` |
| Kit-Stempel 11.–26.09. | über 40 | Rundenlog |
| Feld synaipse: Freigaben | 26 in ~36 h (18 scope, 9 in 3½ Min.) | `synaipse-unified/project_memory/approvals/` |
| Feld synaipse: Aufträge | 114 aktiv (67 READY, 30 DONE, 9 VALIDATED, 5 FAILED); 26 QA-Aufträge | `synaipse-unified/project_memory/tasks/active/` |
| Feld synaipse: Commits seit 25.09. | 87 auf main (53 nur Buchführung); 18 Produkt-Commits über alle Branches | `git log` |
| Feld synaipse: Lückenmeldungen | 22, davon 12 Sackgassen, 2 vom eigenen Kostenhebel verursacht (FR-0093-Zeile) | `staging/generation-6/harvest-synaipse-2026-09-26.txt` |
| Feld synaipse: Handwerksgedächtnis Frontend | 104 Dateien bei Budget 20 → eingefroren | `synaipse-unified/.claude/agent-memory/frontend-developer/` |
| Nutzungslimit-Abbrüche | 3 (25.09., 26.09., 27.09.) | Rundenlog |
