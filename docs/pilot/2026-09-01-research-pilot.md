# Research-Team — erster Pilot (FR-0029/FR-0042, TSK-0103), Befunde

Das research-team hatte nie einen Piloten gesehen: die Piloten 1–3 fuhren das dev-team, Pilot 4
zusätzlich das office-team (Hälfte 3). Dies ist der erste Lauf über die Forschungskette.

**Gemessener Stand:** Worktree `stream/research` auf `c155a5f` (Stream D des DEC-0057-Parallel-
Piloten), research-team-Kit vor dem Lauf `2026.08.31-3`. Rohdaten, Treiberskripte und alle
Wortlaute vollständig unter `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0103\`; die beiden
Versuchsprojekte liegen dort als `rig\proj` (Onboarding-Variante) und `rig2\proj` (frisch
aufgesetzt, Kette bis ans Ende). Datum der Messungen: 2026-09-01.

## Angemeldete Abweichung vom Muster der dev-Piloten — bitte zuerst lesen

**Dies ist ein APPARAT-Pilot, kein Persona-Pilot.** Die Piloten 1–4 fuhren echte
`claude --print`-Sitzungen mit einer Persona und einem getauschten globalen Kit-Speicher
(`docs/pilot/2026-08-09-plan.md`, „Ablauf"). Gefahren wurde er hier nicht, und die Gründe sind
verschieden stark: der Auftrag dieses Streams verbietet jede globale Installation, und ein
Persona-Lauf misst Modellverhalten, das ein Stream-Umsetzer nicht abnehmen kann. **Nicht** dazu
gehört die Behauptung, ein Persona-Lauf sei technisch unmöglich gewesen: das Rig hier zeigt,
dass ein Wegwerf-HOME den globalen Speicher gar nicht anfasst — ob `claude --print` ein
getauschtes HOME/`CLAUDE_CONFIG_DIR` annimmt, ist in dieser Runde schlicht **nicht gemessen**.

Gefahren wurde stattdessen: ein Forschungsprojekt frisch aufgesetzt (`init_project_memory.sh` +
`scaffold_team.sh` gegen ein Wegwerf-HOME unter dem Scratch), und danach **jeder Schritt der
Phasen 0–10 der Verfassung als echter Prozess** — `python scripts/harness.py …` als Einstiegspunkt,
die installierten Haken über `_gate.py` mit JSON auf stdin, so wie `settings.json` sie registriert.

**Was diese Methode NICHT messen kann, und was daran hängt:** die besten Befunde der dev-Piloten
waren Verhaltensbefunde (P4-2 Leerlauf, P4-5 „auf deinem Desktop", B5 Fachjargon-Leck). Solche
Befunde kann dieser Lauf nicht erzeugen. Er misst, **was ein PM tun kann und woran er stehenbleibt** —
und genau davon hat er sieben Stellen gefunden. Ein Persona-Lauf für das research-team bleibt offen
und ist mit FR-0029 nicht erledigt.

## Der Verlauf in einem Satz

Onboarding, Scope-Freigabe, Liefer-Freigabe, Hypothese, Experiment, Aufgabe, Kind-Spawn,
Ergebnis-Umschlag, Evidenz, Merge, Abnahme — **die Kette läuft durch**, aber nicht auf dem Weg, den
die Verfassung beschreibt: an genau einer Stelle muss der PM von der dokumentierten Hierarchie
abweichen, und die Stelle sagt ihm nicht, wie.

---

## R1 — Die dokumentierte Kette `RQ → HYP → EXP → TSK` lässt sich nicht anlegen

§4 der Verfassung: „User wish → `RQ` → `HYP` → `EXP` → `TSK`". Genau das wurde gefahren:
`RQ-0001` freigegeben, `HYP-0001` daraus, `EXP-0001` aus der Hypothese, dann die Aufgabe.

```
$ python scripts/harness.py create-task --product-requirement RQ-0001 \
      --derives-from EXP-0001 --type research --assigned-role researcher --acceptance-ref AC-1 ...
rc=1
derives_from EXP-0001 belongs to HYP-0001, not to this task's root RQ-0001 -- refused at
creation (spec II.8). ...
```

Ursache, gemessen: `kernel/report._root_of` beantwortet „woran hängt dieses Item" mit dem
**einen unmittelbaren Elternteil** (`parents[0] if len(parents) == 1 else None`), während
`kernel/report._hangs_from` dieselbe Frage **transitiv** beantwortet. Beide Antworten für dasselbe
Experiment:

```
HYP-0001 parents=['RQ-0001']  _root_of=RQ-0001    _hangs_from(RQ-0001)=True
EXP-0001 parents=['HYP-0001'] _root_of=HYP-0001   _hangs_from(RQ-0001)=True
```

Das dev-Kit trifft das nie: dort ist jeder Aufgaben-Ursprung genau eine Ebene unter der Wurzel
(`PR → SR → TSK`, `PR → BUG`, `PR → CR`). Das research-Kit ist das einzige ausgelieferte Kit, dessen
Kette tief genug ist, dass die beiden Leser auseinanderfallen — deshalb hat es nie ein Test gesehen.

Nicht behoben in DIESER Runde (Kernel gehört nicht diesem Stream). Der Test, der die Stelle
hält, ist `tools/test_research_chain.py::test_a_task_may_name_an_experiment_two_levels_under_the_question_it_serves`
-- er maß damals das Gegenteil als geltendes Verhalten und sagte im eigenen Docstring, dass er am
Tag der transitiven Auflösung umzudrehen sei; mit `BUG-0083` ist das geschehen, und der Name, den
dieser Bericht am 2026-09-01 nannte, gibt es seither nicht mehr.

## R2 — Der Ausweg, den die Verweigerung nennt, endet zwei Schritte später in einer Sackgasse

Die Verweigerung aus R1 nennt einen Ausweg: „Remedy: create the task under HYP-0001". Gefahren:

```
$ ... create-task --product-requirement HYP-0001 --derives-from EXP-0001 ...
rc=0   TSK-0002 DRAFT (researcher)
$ python scripts/harness.py validate
rc=0   0 error(s), 0 warning(s)
$ python scripts/harness.py dispatch TSK-0002
rc=1
no user approval authorises dispatching TSK-0002 under HYP-0001 -- blocked (spec II.2 ...).
Remedy: obtain the scope approval for HYP-0001, ...
```

Damit steht eine Hypothese im Feld `product_requirement`, dessen eigene Hilfe „the PR/RQ root this
task serves" sagt, der Validator nimmt es an — und der Dispatch verlangt eine Freigabe auf einer
`HYP`. §4 derselben Verfassung sagt über die `HYP`: „carries no approval of its own"; der Kernel
sagt es an zwei Stellen ebenfalls (`backlog_types.INVALIDATION_TARGET`: „HYP deliberately absent";
`approvals.APPROVAL_TRANSITIONS` kennt kein `HYP`-Paar).

Gemessen ist der Ausweg trotzdem begehbar — was ihn schlimmer macht statt besser:
`request-approval scope HYP-0001` läuft rc 0, der Haken prägt `APR-0004`, und der Dispatch geht auf.
Der PM landet also über einen Weg, den seine Verfassung ausdrücklich für nicht existent erklärt.

## R3 — Diese Freigabe auf einer `HYP` wird nie ungültig

`backlog_types.HASHED_FIELDS` führt kein `HYP`. Also bewegt eine Änderung am Inhalt der Hypothese
weder Revision noch Freigabe. Beide Richtungen in einem Lauf gemessen:

```
$ harness update HYP-0001   {"statement": "GEAENDERT: eine feste Chunk-Groesse ist besser."}
   HYP-0001 PROPOSED rev 1 approval_ref: APR-0004        <- Freigabe bleibt stehen

$ harness update RQ-0001    {"motivation": "GEAENDERT"}
   RQ-0001 DRAFT rev 2 approval_ref: -                   <- Freigabe fällt, Status fällt zurück
```

In Verbindung mit R2 heißt das: die eine Freigabe, die auf dem einzig dokumentierten Weg jeden
Forschungs-Dispatch aufsperrt, deckt jede spätere Umschreibung der Hypothese mit ab. Wer die
Hypothese nach der Freigabe umdreht, dispatcht weiter unter der alten Zustimmung. Nicht behoben
(Kernel).

## R4 — Die Ursprungsprüfung fällt bei mehrdeutiger Elternschaft OFFEN aus (H95)

Es gibt einen zweiten Weg, und er ist der, auf dem der Kettentest läuft: hängt das Experiment an
**beiden** Eltern, liefert `_root_of` `None` (`len(parents) != 1`), die Ursprungsprüfung wird
übersprungen, und die Aufgabe entsteht unter der Forschungsfrage.

```
$ harness capture EXP  {"derives_from": ["HYP-0001", "RQ-0001"], ...}
   EXP-0002 DESIGNED         _root_of(EXP-0002) = None
$ ... create-task --product-requirement RQ-0001 --derives-from EXP-0002 ...
   rc=0   TSK-0003 DRAFT (researcher)
```

**Ich hatte das als „Umweg, der mit R1 verschwindet" abgetan. Der Prüfer hat nachgemessen, dass
beides falsch ist**, und damit ist es ein eigenes Loch, **H95**:

* Es ist **kein Umweg, sondern ein Durchlass**. Ein Experiment mit zwei Eltern unter `RQ-0001`
  lässt eine Aufgabe unter einer **fremden** Wurzel `RQ-0002` anlegen: `create-task` rc 0,
  `validate` 0 Fehler. Dieselbe Anlage einelterig → rc 1. Die Prüfung, die verhindern soll, dass
  eine Aufgabe gegen die Kriterien einer fremden Wurzel gemessen wird, gibt bei Mehrdeutigkeit auf
  (`report.py:934-941` gibt `None`, `dispatch.py:176-177` überspringt bei `if origin_root and …`).
* Es ist **nicht research-spezifisch**: jeder Typ, dessen Bindungsfeld eine **Liste** trägt, kann
  das — `SR.derives_from` zum Beispiel. Alle Kits.
* Es **verschwindet nicht mit R1**: der Prüfer hat R1 im Klon geschlossen (transitiver Term) und
  der Weg blieb rc 0.

Nicht behoben (Kernel).

## R5 — `report_lint.py` findet die Berichte nicht dort, wo das Kit sie rendert — **behoben**

`scripts/report_lint.py` ist die einzige Stelle im Kit, die einen gerenderten Bericht überhaupt
liest. Vor dem Lauf suchte sie so:

```python
subprocess.run(["git", "-C", ROOT, "ls-files", "reports", "evidence"], ...)
... if line.strip().lower().endswith((".md", ".txt"))
```

Zwei unabhängige Fehler, beide gemessen in einem frisch aufgesetzten Projekt:

* **Der Ort.** §6 legt die Berichte nach `project_memory/reports/`. Der Pfadausdruck fragt git nach
  `reports` und `evidence` **an der Repo-Wurzel**. `git ls-files reports evidence` → leere Ausgabe,
  während `git ls-files project_memory/reports` das gefüllte Fach listet. Ergebnis mit drei
  überzogenen Berichten darin: `[report_lint] no reports to check.`
* **Das Format.** §17 nennt `reports/EXP-*.{tex,pdf,html}`. Die Endungsliste kennt nur `.md`/`.txt`.
  Gegenprobe an der Repo-Wurzel, beide Dateien mit demselben Satz: `reports/EXP-0009.md` wurde
  gemeldet, `reports/EXP-0009.tex` nicht.

Behoben in diesem Stream, als Eigenschaft statt als Pfad- und Endungsliste: ein Bericht liegt
**unmittelbar** in einem Verzeichnis namens `reports` (ein Unterverzeichnis eines solchen Fachs
trägt die Render-Zutaten — Schriften, KaTeX —, keine Ergebnisbehauptungen), und seine Bytes
**dekodieren als UTF-8** (so fällt das gerenderte PDF heraus, ohne genannt zu werden; das `.tex`
daneben trägt dieselben Sätze). Gefragt wird git mit `--cached --others --exclude-standard`, damit
ein gerade erst gerenderter Bericht schon auf dem Durchgang gesehen wird, der ihn rendert (§17), und
`.gitignore` entscheidet, was Build-Ausgabe ist. `evidence` ist ersatzlos entfallen: Evidence-Items
sind YAML, die Endungsliste daneben hat dort nie etwas getroffen.

### R5a — was der Fix selbst kaputt gemacht hätte, gemessen und mitgeschlossen

Sobald das Fach gefunden wird, liest die Prüfung auch das, was das Kit selbst hineinlegt. Gemessen
an `experiment_report.template.html`:

```
experiment_report.template.html            1 finding(s)
   line 44  result without an n  '100%'
```

Zeile 44 ist eine CSS-Regel (`table { … width: 100%; … }`). Das trifft nicht nur die Vorlage: ein
**gerenderter** HTML-Bericht trägt denselben `<style>`-Block, also hätte mein Fix jedem
Forschungsprojekt einen sinnlosen Befund in jeden Pipeline-Lauf gelegt — dauerhaft. Geschlossen
durch eine Eigenschaft im selben Sinn: **Markup ist keine Behauptung.** `<style>`/`<script>`-Blöcke
und Tags werden vor der Prüfung ausgeblankt, Zeilenumbrüche bleiben stehen, damit ein Befund
weiterhin seine echte Zeile nennt.

**Der erste Anlauf war falsch, und der Prüfer hat ihn gemessen.** Er band ein Tag an die Zeile
(„ein Tag darf keine Zeile überspannen") — und damit galt **jedes `<`…`>`-Paar in EINER Zeile** als
Tag. Das trifft Prosa mitten ins Ergebnis:

```
Bei Werten < 30 stieg der Anteil auf 95% in Gruppen > 10 Personen.   -> KEIN Befund
Bei Werten unter 30 stieg der Anteil auf 95% in vielen Gruppen.      -> Befund      (Kontrolle)
Fuer $n < 400$ proves der Arm die Wirkung, $d > 0{,}8$.              -> KEIN Befund
Fuer n gleich 400 proves der Arm die Wirkung.                        -> Befund      (Kontrolle)
```

Meine eigene Gegenprobe hatte das nicht gesehen, weil sie die **einzige** Schreibweise ohne
schließendes `>` prüfte. Und die Zeilengrenze war auch in der Gegenrichtung falsch: ein echtes
`<table` mit umgebrochenen Attributen (`<table\n   style="width: 100%">`) blieb Markup, das
niemand ausblankte — Befund `result without an n ('100%')` auf einer Tag-Zeile.

Ersetzt durch die Eigenschaft, die ein Tag wirklich hat: **hinter `<` steht ein Namensbuchstabe**,
und bis zum schließenden `>` kommt kein zweites `<`. Damit fällt `< 30 … >` als Prosa heraus,
`<p>` und `<table style=…>` weiter als Markup, und ein Tag darf über Zeilen gehen. Nachgemessen:
alle vier Zeilen oben ergeben jetzt ihren Befund, der umgebrochene `<table>`-Tag keinen, und beide
ausgelieferten Vorlagen 0 Befunde.

**Was auch die neue Regel noch ausblankt und nicht sollte** — und das steht so im Code, nicht als
Schutzbehauptung: Prosa, deren `<` von einem **Buchstaben** gefolgt und später geschlossen wird,
`wenn x<y und z>0`. **Und „später" reicht weiter, als meine erste Formulierung zugab** (Prüfer):
die Regel läuft mit `DOTALL`, ein solches Paar darf also mehrere Zeilen auseinander liegen, und
die ganze Prosa dazwischen verstummt — gemessen an einem `x <` in Zeile 1 und einem `> 0` in
Zeile 4, das drei Zeilen mitnahm, samt der 95-%-Behauptung auf Zeile 2. Die Spanne endet am
nächsten `<`, nicht an der Zeile und nicht am Absatz.

Eine **Längengrenze** war der naheliegende Dämpfer und ist nach Messung **verworfen**: über alle
`.html`/`.md`/`.tex`, die die drei Kits ausliefern, ist das längste echte Tag 70 Zeichen lang und
einzeilig, während die beiden Prosa-Fehltreffer 88 und 220 Zeichen messen. **Die Begründung dieses
Absatzes war zuerst falsch und ist in TSK-0104 korrigiert:** sie sagte „kein Schnitt trennt die
Klassen", und das ist an genau diesen Zahlen widerlegt — jede Grenze zwischen 71 und 87 trennt sie
heute. Verworfen ist die Grenze aus dem allgemeinen Grund: ein echtes Tag hat keine Länge, seine
Attributliste ist unbegrenzt, also ist jede Zahl hier auf EINEN Baum gepasst, und das erste längere
echte Tag irgendwo tauscht einen stillen Fehltreffer gegen einen lauten falschen Befund. Was das
schlösse, ist eine Tag-**Grammatik**, keine Grenze — und die ist größer als das, was in dieser
Runde noch prüfbar war. Steht so im Kommentar der Regel.

### R5b — `report_lint` schrieb cp1252 in die Pipe

Aufgefallen, weil der Kettentest den Bericht bewusst `EXP-0001-Größe-αβ.tex` nennt: die Prüfung fand
ihn, aber der Name kam am Elternprozess als Buchstabensalat an. Ursache: das Skript stellt seine
Ausgabeströme nicht auf UTF-8 um, während `quality.py` es als Unterprozess fährt und seine Ausgabe
liest. Beide Hälften gemessen (cp1252): ein deutscher Name wird zu Mojibake, ein griechischer oder
chinesischer löst `UnicodeEncodeError` beim Schreiben aus und nimmt die Pipeline-Stufe mit, bevor
ein einziger Befund gedruckt ist. Geschlossen mit derselben Schreibweise, die `quality.py` seit
zwei unabhängigen Live-Projekten trägt.

Rot ohne die Fixes, jeweils einzeln zurückgedreht im Klon außerhalb des Repos:

| zurückgedreht | Test | Beobachtet |
|---|---|---|
| alte Pfad-/Endungsliste | `test_a_rendered_report_is_found_where_the_kit_actually_renders_it` | `AssertionError: [report_lint] no reports to check.` |
| Ausgabeströme nicht umgestellt | derselbe Test | Name kommt als Mojibake zurück, Zeile 403 |
| Markup nicht ausgeblankt | `test_the_stylesheet_of_a_rendered_html_report_is_not_read_as_a_result` | `result without an n` auf der CSS-Zeile |

## R6 — Der Test, der `report_lint` bewachte, maß seine eigene Kulisse

`tools/test_hooks.py::test_a_kit_checker_that_declares_a_quality_stage_is_run_by_the_pipeline` baut
sein Prüfprojekt so:

```python
os.makedirs(str(work / "reports"))
write(str(work / "reports" / "final.md"), "The intervention proves the effect ...")
```

Ein `reports/`-Verzeichnis an der Repo-Wurzel mit einer `.md`-Datei — die eine Kombination, die der
defekte Sucher traf, und die einzige Kombination, die ein ausgeliefertes research-Projekt **nicht**
hat. Der Test war grün über die gesamte Lebenszeit von R5. Er misst weiterhin richtig, was er messen
will (dass `quality.py` den Prüfer über seine Deklaration findet); seine Kulisse ist der Fehler.

Nicht in diesem Stream angefasst: `tools/test_hooks.py` liegt außerhalb des `allowed_scope` dieses
Auftrags. Naht-Punkt für die Merge-Runde.

## R7 — Der gerenderte Bericht hat keinen Schreibweg — die Rolle, der er gehört, kann ihn nicht schreiben

§6 gibt `reports/EXP-*.{tex,pdf,html}` und `reports/fzulg_application_RQ-*.md` dem **Report-Writer**.
§17 sagt: „an experiment without its rendered report is INCOMPLETE". §4 lässt den Merge auf
Reviewer-Evidenz auf, und `gate_memory_complete` blockt ihn, solange ein `EXP` in `ANALYZED` ohne
`evidence_refs` steht (unten in R9 gemessen).

Gemessen, was passiert, wenn eine Rolle diesen Bericht schreibt:

```
Write project_memory/reports/EXP-0002.tex                       -> rc=2
Write project_memory/reports/fzulg_application_RQ-0001.md       -> rc=2
Write project_memory/staging/TSK-0001/EXP-0002.tex              -> rc=0
Write reports/EXP-0002.tex                                      -> rc=0
```

Der Wortlaut der Verweigerung: „the TOOL route into such a file does not exist … No
`python scripts/harness.py` command writes this one either, so this write has no route from inside
this session". Der genannte Ausweg — „It is filled by the entry gate BEFORE the kit is installed, or
by the user in an editor outside this session" — passt auf die Masterplan-Klasse von Dokumenten, aber
nicht auf einen Bericht je Experiment, den es beim Onboarding noch nicht gibt.

**§0 der Verfassung ist an dieser Stelle ehrlich** und sagt die Sperre ausdrücklich an („makes no
exception for … the rendered `reports/` §6 assigns to a role"). Was fehlt, ist die Gegenrichtung: §6
und §17 verteilen eine Pflicht, für die es keinen Weg gibt, und nennen den Ort nicht, an dem der
Bericht heute liegen könnte (`staging/<TSK-ID>/` oder ein `reports/` außerhalb des
Zustandsverzeichnisses — beide gemessen rc 0). Nicht behoben, und der Grund ist diesmal nicht die
Ratsche (R8 zeigt, dass eine kürzere wahre Formulierung nichts kostet): der Fix ist entweder ein
Kernel-Schreiber für dieses Fach, oder eine Verfassungsänderung, die einen **Ersatzort** benennt —
und welcher der beiden gemessenen Orte der gesegnete ist, ist eine Produktentscheidung, keine
Umsetzer-Entscheidung. Zur Abnahme durch den Nutzer.

## R8 — Zwei Sätze behaupteten Schutz, den der Code anders baut — **behoben**

Beide standen im research-Kit, beide waren in diesem Stream reparierbar, beide sind repariert. Die
erste Fassung dieses Piloten ließ sie stehen und begründete das mit dem Deckel der
Lead-Paket-Ratsche; der Prüfer hat nachgerechnet, dass die Begründung falsch war: **der Deckel
verbietet Wachstum, nicht Korrektur.** Ein kürzerer wahrer Satz kostet nichts.

**(a) `AGENTS.md` §4, Zeile 94.** Ein `EXP` hat kein Feld `class` — weder in
`REQUIRED_FIELDS["EXP"]` noch in `OPTIONAL_FIELDS`. Der Kernel sperrt `DESIGNED -> APPROVED`
**für jedes** Experiment:

```
$ harness transition EXP-0001 APPROVED
rc=1  EXP-0001 DESIGNED -> APPROVED is the transition a delivery approval commits, and none is
      in force for EXP-0001 at revision 1 -- refused (fail-closed). ...
```

| | Wortlaut |
|---|---|
| vorher | ``EXP` carries the delivery approval at class `large`.` |
| **geliefert** | ``every `EXP` carries the delivery approval.`` |

Getragen als laufende Messung von
`tools/test_research_chain.py::test_every_experiment_needs_a_delivery_approval_whatever_its_size`.

**(b) `AGENTS.md` §2 Punkt 4, Zeile 56.** Der Übergang gelingt; was refüsiert, ist der Validator,
und das Tor, das ihn liest, ist `gate_memory_complete` auf der Merge-Zeile:

```
$ harness transition EXP-0002 ANALYZED                  -> rc=0, evidence_refs: []
$ hook gate_git.py  (git merge rq/RQ-0001-…)            -> rc=0
$ hook gate_memory_complete.py (dieselbe Zeile)         -> rc=2
      EXP-0002: ANALYZED without evidence_refs -- an experiment with no report is incomplete …
```

| | Wortlaut |
|---|---|
| vorher | `an `EXP` may not reach `ANALYZED` without its report in `evidence_refs`.` |
| **geliefert** | `no merge passes an `EXP` in `ANALYZED` without `evidence_refs`.` |

Getragen von
`tools/test_research_chain.py::test_an_experiment_reaches_analyzed_unrefused_and_the_merge_is_where_the_report_is_demanded`.

**Was die Korrektur nach sich zog, und was daran zu lernen war.** Beide neuen Sätze sind kürzer als
die alten, das Lead-Paket ist also geschrumpft — und genau daran ist meine zweite Annahme
gescheitert: der eingetragene Deckel ist keine Obergrenze, sondern **die Messung selbst**
(`test_context_budget::test_the_recorded_ceiling_is_the_measurement_and_not_a_typed_number`), also
muss er auch nach unten neu eingetragen werden. Dazu meldete `test_shortening_net` die beiden
berührten Sektionen als CHANGED. Beide Ratschen sind mit Notiz neu eingetragen; die Zahlen stehen
dort, wo sie hingehören, und **absichtlich nicht hier** — in `tools/lead_package_sizes.json`,
`tools/constitution_section_pins.json` und den Journalzeilen in
`docs/reviews/phase0-disposition.md` (§9 Sektionspin-Journal, §10 Lead-Paket-Größenjournal). Die
Merge-Runde trägt beide erneut ein (DEC-0057 c).

## R9 — Kleinere Stellen, gemessen, ohne Blockade

1. **`solo` installiert keinen `report-writer`.** `presets.yaml`:
   `solo: methodologist researcher reviewer project-auditor` — `duo` hat ihn, `solo` nicht. §6 gibt
   genau dieser Rolle die Berichte, §17 macht sie zur Vollständigkeitsbedingung. Ein
   `solo`-Forschungsprojekt hat also niemanden für einen Artefakt-Typ, an dem der Merge hängt.
   (Zusammen mit R7 ist das derselbe Weg, zweimal versperrt.) Der `research-engineer`, dem §6
   „pipelines/environments/datasets" zuweist, fehlt in `solo` und in `duo`; nur `team: all` hat ihn.
2. **`generate-session-brief` verlangt drei Flags, die der Sitzungs-Hinweis nennt.** Der
   `SessionStart`-Hinweis sagt es korrekt mit; frisch nach dem Scaffold existiert
   `generated/session_brief.yaml` noch nicht, `harness generate-session-brief` ohne Flags ist rc 2,
   mit den Werten aus `harness doctor` rc 0. Kein Blocker, aber der erste Zug jeder ersten Sitzung.
3. **Ein frisch aufgesetztes Projekt verweigert jeden Spawn**, bis eine Sitzung wirklich neu
   startet: `.claude/HANDOVER_PENDING` → `gate_dispatch` rc 2 mit genau diesem Text. Das ist
   gewolltes Verhalten und steht hier nur, weil ein Kettentest ohne diesen Schritt den Marker misst
   statt der Kette — `tools/test_research_chain.py::_install` fährt den `SessionStart`-Haken deshalb
   mit.
4. **`tools/conftest.py::mint_via_hook` prägt über `dev-team/hooks/gate_approval.py`** aus diesem
   Repo. Für die Kette ist das ein anderes Programm als der Haken, den das Scaffold ins Projekt
   legt (byte-gleich heute, aber die Aussage „der installierte Haken prägt" misst es nicht). Der
   Kettentest prägt darum über den installierten Haken und sagt in `Project.mint`, warum.

---

## Zusammenfassung

| Nr. | Stelle | Urteil |
|---|---|---|
| R1 | `_root_of` ist ein Sprung, die Kette ist zwei tief | **offen** — Kernel, Naht |
| R2 | genannter Ausweg endet an einer `HYP`-Freigabe, die §4 verneint | **offen** — Kernel, Naht |
| R3 | diese `HYP`-Freigabe wird nie ungültig | **offen** — Kernel, Naht |
| R4 | Ursprungsprüfung fällt bei mehrdeutiger Elternschaft offen aus | **offen** — **H95**, Kernel, alle Kits |
| R5 | `report_lint` sah kein Fach und kein Format | **geschlossen** in diesem Stream |
| R5a | Markup eines gerenderten HTML-Berichts las sich als Ergebnis | **geschlossen** (vom Fix selbst aufgeworfen) |
| R5b | `report_lint` schrieb cp1252 in die Pipe | **geschlossen** in diesem Stream |
| R6 | der Test dazu maß seine eigene Kulisse | **offen** — `tools/test_hooks.py`, Naht |
| R7 | der gerenderte Bericht hat keinen Schreibweg | **offen** — Kernel oder Verfassung |
| R8 | zwei Sätze (§2 Punkt 4, §4) behaupteten den Schutz anders, als er gebaut ist | **geschlossen** in diesem Stream |
| R9 | `solo`/`duo` ohne `report-writer`; drei Kleinigkeiten | **offen**, ohne Blockade |

**Der Pilot, den FR-0029 eigentlich will — eine echte Sitzung mit einer Persona — steht weiterhin
aus.** Was hier steht, ist die Hälfte, die ohne Modell-Sitzung messbar war.
