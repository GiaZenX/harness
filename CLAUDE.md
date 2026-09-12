# Arbeitsweise in diesem Repo

Dieses Repo ist die **Quelle der Team-Kits**, nicht ein Projekt, das eines benutzt. Es trägt
deshalb bewusst **kein** installiertes Kit und **keinen** Team-Kit-Marker.

Die Marker-Zeichenkette selbst steht in dieser Datei absichtlich **nirgends** — auch nicht in einem
Satz, der ihre Abwesenheit behauptet. Die globale Einstiegsdatei entscheidet über die Übergabe an
einen Projektmanager allein daran, ob `./CLAUDE.md` die Zeichenkette **enthält**; Anführungszeichen
und Verneinung sieht diese Regel nicht. Bis 2026-08-04 stand sie genau in so einem Satz hier.
`.claude/hooks/test_gates.py` misst das.

Der Grund für die Entscheidung ist gemessen, nicht Bequemlichkeit: `gate_write_scope` verweigert
jede schreibende Befehlszeile, die `team-kits` oder `.claude` nennt. In diesem Repo ist **jede**
Änderung eine Änderung an `team-kits/`. Ein installiertes Kit würde seine eigene Entwicklung
stilllegen.

Was dennoch gilt, steht hier. Alles darin ist aus Schaden gelernt; jede Regel hat einen Fall
hinter sich.

## Berichte an den Nutzer: einfache Sprache, kein Fachjargon

Der Nutzer ist kein Entwickler. **Jeder Bericht an ihn ist in einfacher, alltäglicher Sprache** —
so, dass jemand ohne Technikwissen versteht, was passiert ist, warum es wichtig ist, und was als
Nächstes kommt. Das gilt für den Sitzungsagenten gegenüber dem Nutzer; **zwischen den Rollen
(Umsetzer/Prüfer) bleibt die Sprache so präzise und fachlich wie nötig** — dort ist Genauigkeit
wichtiger als Verständlichkeit.

Konkret:

- **Kein Fachjargon ohne Erklärung.** Sätze wie „ein aktives Datenverlust-Loch (H34), quotierte
  Pfade hinter `rm -f` werden als Prosa entfernt und der Operand verschwindet" sind für den Nutzer
  wertlos. Erklär stattdessen das *Was* und *Warum* in Bildern des Alltags („eine Schutzregel hatte
  ein Loch, durch das eine wichtige Datei gelöscht werden konnte — sie ist wiederherstellbar").
- **Item-Nummern bleiben.** `DEC-`, `SR-`, `BUG-`, `TSK-`, `EVD-` usw. darf und soll der Bericht
  nennen — der Nutzer will nachschlagen und mitreden können. Sie sind ein Verweis, kein Ersatz für
  die Erklärung.
- **Erklär, was Werkzeuge und Befehle tun**, wenn du sie erwähnst (was ein „Patch" ist, was ein
  gestoppter Agent war, was ein Befehl bewirkt). Lass den Nutzer nie mit einem Wort zurück, das er
  nicht einordnen kann.
- **Sag klar, was IHN blockiert oder was auf IHN wartet**, in seiner Sprache — Entscheidungen,
  Freigaben, Handbacks —, nicht nur, was den Apparat blockiert.

Der Fall dahinter: Bis 2026-08-11 kamen die Berichte voll technischer Kürzel beim Nutzer an, der sie
nicht verstand und darum nicht mitentscheiden konnte. Verständlichkeit für den Nutzer ist kein
Beiwerk, sondern Voraussetzung dafür, dass er das Projekt lenkt statt nur bezahlt.

**Eine Frage nach dem SOLL wird zuerst gegen `decisions/active/` beantwortet, dann gegen den
Code.** Der gebaute Stand und der beschlossene Zielstand fallen in diesem Projekt regelmäßig
auseinander (die Leiter-Mechanik aus `DEC-0034` etwa ist beschlossen und absichtlich noch nicht
gebaut). Wer nur die gebauten Dateien liest, gibt die halbe Wahrheit als ganze aus — gemessen
2026-08-17, als der Lead die Modell-Frage aus `model_tiers.yaml` beantwortete und `DEC-0034`
unterschlug, bis der Nutzer nachhakte. Also: erst ein Grep über die aktiven Entscheidungen, dann
der Code, und eine Antwort, die nur aus gebauten Dateien stammt, sagt das dazu. Durchsetzen kann
das kein Gate (Freitext sieht keines); tragen muss es diese Regel hier plus die Gegenrichtung —
eine gebaute Datei, die eine Entscheidung verkörpert, nennt ihre `DEC`-Nummer, damit auch der
falsche Einstieg beim richtigen Datensatz endet.

## Die drei Rollen

Es gibt genau drei, und sie werden nicht vermischt:

- **Umsetzer** (`harness-implementer`) schreibt. Er misst jede Behauptung, die er aufstellt.
- **Prüfer** (`harness-verifier`) misst gegen den laufenden Code, greift den **Fix** an statt den
  ursprünglichen Angriff zu wiederholen, und arbeitet read-only in einer Kopie außerhalb des Repos.
- **Der Sitzungsagent** (`harness-lead`, gebunden über `.claude/settings.json` `agent:`)
  **orchestriert nur.** Er schreibt keinen Produktionscode und urteilt nicht über ein Paket, das er
  selbst gebaut hat.

**Es schreibt immer nur einer.** Drei Umsetzer parallel auf einem Arbeitsbaum haben einmal vier
Nähte gekostet — eine Prosafassung, die vom Code wegdriftete, eine Verweigerung mit dem Anker an
der falschen Stelle, eine veraltete Zählung, ein Test auf einer Kommandofläche, die es nicht mehr
gab. Getrennte Dateilisten sind **keine** Isolation.

**Und getrennte Bäume sind keine getrennte Prüfung.** Am 2026-08-04 liefen zwei Umsetzer auf
wirklich disjunkten Bäumen — `.claude/` und `team-kits/`. Die Bäume kollidierten nicht, aber
`python -m pytest tools/` spannt über beide: neun Tests fielen, sieben davon nur, weil der eine
Umsetzer `team-kits/` änderte, während der andere seinen Abschlusslauf fuhr. **Keiner von beiden
konnte eine grüne Suite liefern**, und der Zweite hat richtig entschieden, `bump_kit_version.py`
NICHT zu fahren — das hätte eine fremde, laufende Änderung gestempelt. Parallel darf also nur
laufen, wer keine Abnahme über die gemeinsame Suite braucht.

## Die Hausregeln

**Definitionen statt Aufzählungen.** Eine Liste von Fällen ist eine Behauptung darüber, dass die
Welt nicht mehr Fälle hat. Wo eine Aufzählung unvermeidbar ist, bekommt sie einen Stolperdraht,
der **beide** Enden misst: der Eintrag ist tot, und der Eintrag wäre gar nicht nötig gewesen.

**Eine Prüfung muss den Teil lesen, der läuft** — geparst oder ausgeführt, nie eine Zeichenkettensuche
über eine Datei. Ein Test, der eine Datei nach einem Satz durchsucht, misst die Datei, nicht das
Verhalten.

**Kein Kommentar darf Schutz behaupten, den der Code nicht baut — und der Satz soll gar nicht erst
entstehen.** Die reaktive Hälfte: bleibt eine Lücke, wird die Lücke hingeschrieben, nicht der Satz
gerettet. Die präventive Hälfte ist die, die hier Runden gekostet hat: eine Behauptung über eine
**Eigenschaft** wird ein **Test**, und der Kommentar nennt ihn — damit steht sie erst gar nicht als
Prosa da, die jemand später einfangen muss. Was ein Kommentar tragen darf, in welcher Reihenfolge
die drei Fälle geprüft werden und warum eine Zahl an genau einem Ort steht, führt `SR-0008`
(Anlass und Messung: `DEC-0008`) — hier steht es absichtlich **nicht** noch einmal: eine zweite
Fassung überlebt die erste, und genau das ist der Defekt, den die Regel meint.

Unter `.claude/hooks/` ist die eine Hälfte davon gebaut statt versprochen: ein **Testname**, den
eine Aussage dort in Backticks nennt, muss auflösen — sonst wird `test_gates.py` rot. Was als
Nennung zählt, entscheidet dort `test_gates._points_into_this_file` und nicht dieser Satz; der
Leser nimmt die Verzierung ab (Klammern, Satzzeichen, Fettung, die Fall-Id eines parametrisierten
Tests) und sagt in seinem eigenen Docstring, welche Schreibweise er **nicht** liest. Nicht gebaut
ist die andere Hälfte: dass eine Eigenschaftsbehauptung überhaupt einen Test nennt, und ein Name,
der ohne Backticks dasteht — beides bleibt Sache des Umsetzers und des Prüfers. Für `CLAUDE.md`
selbst gilt nur der Zeiger auf Code (`test_gates.py` misst auch den), nicht der auf einen Test.

**Jeder Fix braucht einen Test, der ohne ihn rot wird.** Nicht behauptet: den Defekt in einem Klon
**außerhalb** des Repos wiederherstellen, den Test fahren, rot **sehen**, zurücksetzen. Ein Test,
der nicht scheitern kann, ist teurer als kein Test — er behauptet Deckung.

**Eine Lücke, deren Angriffskette innerhalb einer Sitzung durchläuft, ist blockierend — und
blockierend heißt geschlossen ODER mit einer benannten, vom Nutzer abzunehmenden Ausnahme.** Die
Ausnahme sagt zwei Dinge: **warum** die Lücke nicht schließbar ist, und **was stattdessen begrenzt**.
Ein dritter Zustand („bekannt, kommt später") existiert nicht — das ist der Zustand, in dem eine
Lücke hier dreimal eine Runde überlebt hat. Jeder offene Eintrag der Löcherliste in
`docs/POST_V2_WISHLIST.md` trägt darum Mechanismus, gemessene Kette und Urteil, und bei „nicht
schließbar" die Begrenzung dazu.

**Gespiegelte Dateien bleiben byte-identisch**, außer `KIT_SPECIFIC_HOOKS` nennt den Grund. Ein
blinder Spiegel hat einmal 119 Zeilen gelöscht.

**Erst `python tools/bump_kit_version.py`, dann urteilen.** Ein Paket ohne Versionsstempel ist
nicht fertig.

**Der Testumfang einer Runde richtet sich nach dem, was sie berührt** (`DEC-0050`). Während einer
Runde laufen die betroffenen Suiten; die volle Suite ist ein **Lieferkriterium** und läuft
**einmal** — nach der letzten Nacharbeit, vor Stempel und Commit. Der Prüfer fährt sie gar nicht:
seine Aufgabe ist die Messung gegen den laufenden Code, nicht die Wiederholung eines Laufs, den
der Umsetzer protokolliert hat; nachrechnen muss er. Der rote Test bleibt Pflicht für **jeden**
blockierenden Fix — gekürzt wird die Wiederholung, nie die Strenge. Der Fall dahinter ist
gemessen: an `TSK-0083` lief die volle Suite in sechs Runden mit, 35 bis 39 Minuten je Lauf, rund
vier Stunden, und **kein einziger Befund einer Runde kam aus ihr** — alle kamen aus dem Messrig
und den Mutationsläufen. Ein Auftrag, der „volle Suite" ohne diesen Zeitpunkt verlangt, ist ein
Auftragsfehler des Sitzungsagenten und wird als solcher benannt; genau der ist dort passiert.
Durchsetzen kann das hier kein Gate — die Stelle, die es messen könnte, liegt in `.claude/` und
ist dem Sitzungsagenten verschlossen. Dieselbe Frage auf der Kit-Seite trägt `FR-0057`.

**Kein Push ohne ausdrückliche Freigabe des Nutzers.** Commits sind Routine, Push nie.

**Alle Arbeitsverzeichnisse außerhalb des Repos liegen unter
`C:\Offline Repos\v2-testbed\_round-scratch\<TSK-ID>\`** — nicht auf der Laufwerkswurzel, nicht
in `C:\tmp`, nicht im Home-Verzeichnis. Der Fall dahinter: Bis 2026-08-18 hatten Umsetzer und
Prüfer über Wochen mehr als zwanzig Scratch-Verzeichnisse wild auf dem Laufwerk des Nutzers
verteilt, weil die Aufträge nur „außerhalb des Repos" sagten. Jeder Auftrag an eine Rolle nennt
den Pfad seither ausdrücklich; aufgeräumt wird beim Rundenabschluss.

## Der Zustand dieses Projekts

`project_memory/` im Wurzelverzeichnis wird vom **Kernel** geführt (`team-kits/kernel`), direkt
aufgerufen, ohne Kit:

```
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory <kommando>
```

Das ist seit 2026-08-05 nicht mehr nur Verabredung: Gate 1 verweigert jedem Aufrufer den
Werkzeug-Schreibzugriff auf den kanonischen Teil von `project_memory/`. Der Grund ist gemessen —
ein von Hand geschriebenes `evidence/active/EVD-*.yaml` mit `result: pass` und dem aktuellen
Diff-Hash öffnete `git commit` auf der Stelle. `project_memory/staging/<item-id>/` bleibt offen;
dort liegen Vorschläge, die noch kein Zustand sind.

Es gibt hier **keine Leases und kein Dispatch**: der Kernel wird direkt aufgerufen, ohne den
Dispatch-Wächter eines Kits, und eine Lease, die nichts durchsetzt, ist eine Lüge im Zustand.

**Die Regel, die alles trägt:**

> Der Auftrag an den Umsetzer wird **aus dem Item erzeugt**, nicht frei geschrieben. Der Prüfer
> bekommt dasselbe Item und meldet jede Abweichung des Pakets von dessen `expected_outputs` als
> Befund.

Damit ist ein Item kein Beiwerk, sondern Eingabe: ein veraltetes Item erzeugt einen falschen
Auftrag, und der Fehler wird sichtbar statt still zu bleiben. Dieselbe Regel wie oben — die
Prüfung muss den Teil lesen, der läuft.

## Die Gates dieses Repos

Seit `SR-0006` (2026-08-04; heute abgelöst durch **`SR-0009`**, das den Auslöser als Eigenschaft
und den Bereich als Ableitung fasst) steht die Regel nicht mehr allein auf Disziplin.
`.claude/settings.json` registriert eigene
Gate-Skripte aus `.claude/hooks/` — kein installiertes Kit, und von den Kit-Hooks genau einer: `gate_approval.py` steht zweimal darin (`AskUserQuestion` vor und nach dem Werkzeug) und wird dort referenziert, wo es ausgeliefert wird, weil eine Kopie davon die Prägung nicht mehr erlauben würde (`.claude/settings.json` sagt im eigenen Kopf, warum). **Wie viele es sind, steht hier
absichtlich nicht**, sondern nur in der Tabelle unten, und die wird gegen die Registrierung
gemessen: `.claude/hooks/test_gates.py::test_the_gate_table_of_this_file_is_the_registration_itself`
liest beide Seiten und wird in beide Richtungen rot. Bis 2026-09-12 stand hier „vier", während fünf
registriert waren und die Tabelle vier Zeilen hatte — eine Zahl in der Prosa altert am Tag, an dem
ein Gate dazukommt (`BUG-0268`).

**Was beim Sitzungsstart bindet, ist die Registrierung** — welches Skript auf welchem Ereignis
läuft, und die `agent:`-Bindung. Die **Dateien** werden bei jedem Aufruf frisch gelesen: ein
geänderter Hook wirkt sofort, und ebenso jede Datei, die ein Hook seinerseits liest — die
Frontmatter einer Rolle zum Beispiel (gemessen: Spawn rc 2 → `harness_item: none` geschrieben →
derselbe Spawn rc 0). Wer „bindet beim Sitzungsstart" als „Inhalt wirkt erst morgen" liest, hat
genau die Lücke vor sich, die 2026-08-05 als F4 gemeldet wurde.

**Jeder Eintrag in `.claude/settings.json` nennt ein `timeout`, und das ist Pflicht.** Ein Hook,
der noch entscheidet, wenn die Frist abläuft, wird getötet — und einen getöteten Hook liest der
Provider als „hook error, carry on", also als **Durchlass**. `_harness.Deadline` liest die Frist
aus genau dieser Datei und verweigert jeden Aufruf, für den sie keine nennt. Wer einen Hook ohne
`timeout` einträgt, legt damit alle Aufrufe dieses Ereignisses still; die Verweigerung sagt es.

**Die Frist wird von außerhalb der Entscheidung durchgesetzt**, nicht von den einzelnen Stellen, die
lange brauchen können: `_harness._the_budget_is_spent` läuft neben jedem Gate und beendet den
Prozess mit einer Verweigerung, sobald das Budget verbraucht ist. Man trifft das als Verweigerung
nach rund vier Fünfteln der registrierten Zeit, mit der Bitte, den Aufruf zu teilen. Was so **nicht**
unterbrochen werden kann, ist ein einzelner laufender Aufruf nach C; das steht mit seiner Messung als
`H36` in `docs/POST_V2_WISHLIST.md`.

Was jedes Gate genau prüft, steht in seinem Kopfkommentar; hier nur, was man wissen muss, bevor man
auf eine Verweigerung trifft:

| Gate | Ereignis | Verweigert |
|---|---|---|
| `gate_lead_write_scope.py` | `Write\|Edit\|MultiEdit\|NotebookEdit` **und** `Bash\|PowerShell` | dem **Sitzungsagenten** jeden Schreibzugriff auf einen geschützten Bereich (unten), **jedem** einen Schreibzugriff auf kanonischen Zustand. Beide Ereignisklassen, weil ein Schreibzugriff durch beide geht: mit nur den Schreibwerkzeugen registriert erreichte eine einzige Bash-Zeile jeden geschützten Pfad (gemessen 2026-08-05, acht Zeilen rc 0) |
| `gate_spawn_needs_item.py` | `Agent\|Task` | einen Spawn, der kein offenes Item nennt — außer die Definition der gespawnten Rolle erklärt `harness_item: none` |
| `gate_commit_evidence.py` | `Bash\|PowerShell` | `git commit`, solange kein aktives `EVD` mit `result: pass` den Diff-Hash des Arbeitsbaums nennt — und jede Zeile, deren Teil vor dem Commit nicht **nachweislich nur liest**. Was das heißt, entscheidet `gate_commit_evidence._moves_the_tree_first`, und zwar mit der Einstufung der Kits: die Umleitung der committenden Stufe zählt dazu (die richtet die Shell vor `git` ein), und seit TSK-0019 auch der Befehl, den eine **Kommandoersetzung** in ihr einführt (`_harness.command_line`). Das ist keine Vollständigkeit, sondern hat **zwei** gemessene Grenzen, und beide lassen durch: ein Schreibzugriff, den die Einstufung der Kits als lesend führt (H22), und eine quotierte Spanne hinter einer **Flagschreibweise**, die die Kits als Prosa entfernen, bevor irgendjemand sie liest — unabhängig vom Verb, also auch ohne jede Ersetzung (H34, und H32 als ihr Sonderfall) |
| `gate_test_scope.py` | `Bash\|PowerShell` | eine Befehlszeile, die eine ganze erklärte Testfläche fährt, ohne das Präfix `DELIVERY_RUN=<ITEM-ID>` zu tragen — der volle Lauf gehört dem Item, das mergt, nicht einem Strom (`DEC-0050`, `FR-0086`). Eine **Auswahl** beurteilt es nicht; was als Verengung zählt, steht in `tools/test_surface.json` und nicht hier |
| `gate_todo_items.py` | `TodoWrite` | eine Aufgabenliste mit mehr als einem Eintrag ohne Item-Id, oder mit einer Id, die nichts Offenes führt |

**Geschützt ist, was den Durchsetzungsapparat oder das Produkt trägt**, und zwar als Ableitung, nicht
als Liste — `_harness.ProtectedArea` ist die Autorität, hier steht nur, woraus sie es ableitet:
alles, was in einen Kit-Hash eingeht (`tools/bump_kit_version.py` + `kernel.hashing`); `.claude/`
als Ganzes, weil der Provider genau dort nachliest, *was* läuft, *wer* läuft und *was er darf*;
jede Datei, aus der das Gate seine eigene Antwort berechnet hat — darunter der Stempler selbst, denn
wer ihn überschreibt, schaltet den Schutz ab, ohne einen geschützten Pfad anzufassen; und
`project_memory/` außer `staging/`, für **jeden** Aufrufer, weil dort das Beweismittel liegt, mit dem
Gate 3 urteilt.

**`tools/` ist damit nicht mehr pauschal frei** — geschützt ist die Datei, aus der abgeleitet wird,
nicht das Verzeichnis. Ein *neues* File neben ihr bleibt schreibbar; das steht als Loch in
`docs/POST_V2_WISHLIST.md`, nicht als Schutzbehauptung hier.

Frei ist alles, was keine dieser Eigenschaften hat — **mit gemessenen Ausnahmen, und die ersten
beiden stehen hier, weil sie einen treffen, der nur liest.** Die erste: ein Kandidat, der einen **Vorfahren** eines
geschützten Baums nennt (ein einzelnes `..`, ein bloßer Laufwerksbuchstabe, die Repo-Wurzel), wird
als Schreibzugriff auf alles darunter gelesen und verweigert: `cp -r docs ..` ist rc 2 (`H19`). Die
zweite: nach einer **Verzeichnisbewegung, die das Gate nicht ausrechnen kann**, ist seine Position
unbekannt, und dann wird **jedes** relative Wort einer schreibfähigen Stufe verweigert — auch eines,
das auf einen freien Pfad zeigt, und für jeden Aufrufer. Auf diesem Host trifft man das zuerst an
einem absoluten Pfad in POSIX-Schreibweise (`cd /c/…`), den Git Bash betritt und kein
Windows-Prozess: gemessen von rc 0 auf rc 2, während `cd "C:/…"` rc 0 bleibt (`H20`). Die dritte
trifft, wer schreibt: ein Wort, dessen **Tilde-Präfix** nicht leer ist, wird für jeden Aufrufer
verweigert, weil eine Shell es aus ihrem eigenen Zustand auflöst und dieses Gate den nicht hat —
auch dann, wenn es auf einen freien Pfad zeigt (`H33`). Was hier ein Präfix ist, sagt
`_harness._tilde_prefix` und nicht die Shell, und die beiden fallen auseinander: `~\+/…` ist der
Shell ein Präfix mit einem quotierten Zeichen und bleibt literal, diesem Leser das **leere**
Präfix, weil der Backslash bei ihm ein Trennzeichen ist — gemessen 2026-08-08 gegen ein
Stellvertreterprojekt außerhalb des Heimatverzeichnisses **rc 0**. Das leere Präfix (`~/…`) bleibt.
**Wo im Wort sonst noch Quotierung steht, ändert daran nichts**, und
das ist gebaut, nicht angenommen: eine Shell entfernt Quotierung zeichenweise, also unterdrückt nur
eine Quotierung **im Präfix selbst** die Erweiterung — und dann bleibt das Wort auch in der Shell
literal. Bis 2026-08-07 stand dieser Absatz hier, während ein `"` hinter dem Präfix genügte:
`sed -i "s/a/b/" ~+/"team-kits"/kernel/state.py` war rc 0, und `bash` schrieb die Datei. Die
vierte ist seit TSK-0098 keine Über-Verweigerung, sondern der Punkt: eine
Befehlszeile, die eine **Haken-Datei startet** — Provider-Baum oder ein `hooks/`-Verzeichnis der
Kits, als Ableitung, nicht als Liste —, wird **jedem** Aufrufer verweigert, auch dem, der sonst
schreiben darf. Wer den Haken von Hand fährt, spielt den Provider und prägt eine Freigabe, die
niemand erteilt hat; genau diese Zeile war bis dahin rc 0 und ist die gemessene Kette von H80. Was
als „starten" zählt, sagt `_harness._executed_words`, nicht dieser Absatz, und dazu gehören seit den
Prüfrunden vom 2026-08-31 auch ein Wort, dessen Pfad die Shell erst herstellt (`$p`,
`$(pwd)/…`, `te*m-kits/…`), ein Starter vor dem Interpreter (`nohup`, `timeout`, `xargs -a`) und
PowerShells Aufrufoperator mit einem Ausdruck. **Zwei Folgen treffen auch, wer nichts Böses
vorhat:** ein Wort mit `$`, `*`, `?`, `[` oder `{` wird unplatzierbar und verweigert — aber nur
dort, wo es überhaupt einen Pfad benennen könnte (`_could_name_a_path`), weshalb `[ $i -ge 3 ]`
einer Warteschleife rc 0 bleibt; und eine Shell-Zeile, die eine Haken-Datei **direkt** benennt,
pflegt sie nicht mehr — kopieren, verschieben, löschen, `sed -i` sind jedem verweigert, während
`Edit`/`Write` dieselbe Datei einem Subagenten offenhalten. Was H80 offen lässt, steht dort mit
Messung: ein selbst geschriebenes Skript prägt weiter (H11), und ein kopiertes
Haken-**Verzeichnis** ebenfalls. Die ersten drei
sind Über-Verweigerung, kein Loch, und alle stehen mit ihrer Kette in
`docs/POST_V2_WISHLIST.md`. Was das ansonsten heute konkret trifft, sagt das Gate,
nicht dieser Absatz — eine Aufzählung hier wäre genau die Behauptung, die schon zweimal eine Datei
zu kurz war.

**Wenn ein Gate selbst kaputt ist, ist es von innen nicht reparierbar** — genau das ist Gate 1. Der
Ausweg steht in jeder Verweigerung: den Fix aus einer Shell **außerhalb** von Claude Code fahren
und die Sitzung neu starten. Die Messung der Gates liegt in `.claude/hooks/test_gates.py` und läuft
**nicht** in `python -m pytest tools/` mit; sie wird ausdrücklich gestartet:

```
python -B -m pytest .claude/hooks/test_gates.py -q
```

## Was ein Auftrag mindestens trägt

Dieselben Felder, die ein `TSK`-Item verlangt, weil sie ohnehin in jedem Auftrag stehen:
erlaubter und verbotener Bereich, benötigte Eingaben, erwartete Ausgaben, die Rolle. Wer sie in
die Nachricht schreibt statt ins Item, schreibt sie einmal für eine Sitzung statt einmal für das
Projekt.

## Wo Dinge hingehören

| Was | Wohin |
|---|---|
| Entscheidung mit Begründung | `project_memory/decisions/active/DEC-nnnn.yaml` |
| Abgelöste Entscheidung | `archive/dec/<jahr>/` — `DEC` hat keinen Automaten, also auch keinen Endzustand; `state.archive()` nimmt automatenlose Typen bedingungslos an. Eine Entscheidung wird nie „fertig", sie wird abgelöst. |
| Wunsch, Idee | dünnes `FR`-Item (`inbox/active/`), `source` zeigt auf den Abschnitt in `docs/` — die Prosa bleibt dort, das Item trägt nur Identität und Stand |
| Anforderung, Aufgabe | typisiertes Item unter `project_memory/` |
| Analyse, Feldbefund | `docs/` |
| Gemessene, offene Lücke | Löcherliste in `docs/POST_V2_WISHLIST.md` |
| Laufender Arbeitsschritt | Aufgabenliste der Sitzung — **genau einer** darf dort ohne Item-Id stehen, jeder weitere Eintrag nennt ein offenes Item (`gate_todo_items.py`) |

Was ausschließlich in einer Aufgabenliste oder in einem Gespräch steht, ist verloren, sobald die
Sitzung zusammengefasst wird. Das ist in diesem Projekt nachweislich passiert.
