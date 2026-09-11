# Zwischencheck TSK-0135 (HALF) — Prüfbericht

Prüfer: `harness-verifier` (Opus, high). Der einzige Zwischencheck eines LARGE-Ziels (DEC-0088 (e)). Als Text
geliefert, vom Lead unverändert hierher gelegt (2026-09-11 03:5x, Uhr gelesen).

**Arbeitskopie:** `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0135/verify/half/` (ohne `.git`, byte-identisch
zum Repo-Stand für alle neun geänderten Kern-/Testdateien — nachgewiesen per `sha256sum`-Diff nach dem letzten
Mutationslauf: *„COPY == REPO for all nine files"*).
**Eigenes Rig:** `…/verify/rig/mutate.py` — verweigert jedes Arbeitsverzeichnis außer dem eigenen (gemessen: `[rig]
refused: this rig runs only from …verify\rig (cwd was …TSK-0135)`, rc 2) und öffnet/schreibt jede Datei **binär**
(`io.open(path,"rb"/"wb")`), stellt nach jedem Lauf die Bytes wieder her und prüft den SHA. Läufe 2026-09-11
03:31:29 – 03:45:00, ein pytest zur Zeit, kein Volllauf.

---

## A. Code-Befunde

### B1 — Der Checkpoint ist *nicht* „never a refusal": eine fehlschlagende Audit-/stdout-Zeile verweigert den Spawn (rc 2) — nach bereits verbrauchtem Lease-Claim
`team-kits/{dev,office,research}-team/hooks/gate_dispatch.py:269` (`_kernel.record_note(HOOK, text)` und der
`sys.stdout.write` darunter stehen **außerhalb** des `try`), Zusicherung in `:254` („Exit 0 either way … not a
blocked spawn") und im Kopfkommentar `:12` („a mirror, never a refusal"); DEC-0092 (3) „It never blocks".

Gemessene Zeile (eigene Mutation B2, `record_note` wirft; der ausgelieferte Hook als echter Prozess gegen ein
Store-Projekt):
```
HOOK rc=2
HOOK stdout: <empty>
HOOK stderr: [team-kit gate_dispatch] internal error (RuntimeError: the audit sink is gone) - refused rather
             than passed, because a crashing hook would otherwise let the call through (spec II.4 fail-closed).
LEASE after the hook: dispatched_at='2026-09-11T03:44:53' claimed=None status='LEASED'
```
Zum Vergleich derselbe Hook unmutiert: `HOOK rc=0` + `additionalContext`; und mit der **Ableitung** als Werfer
(B1-Replay der Rig-Zeile M11b): `HOOK rc=0`. Der Schutz ist also nur für `reflection_checkpoint` gebaut, nicht
für die zwei Zeilen dahinter — und der Spiegel sitzt **hinter** `validate_dispatch(claim=True)`, der Claim ist
verbraucht (`dispatched_at` gesetzt), der Auftrag steht ohne Spezialist auf `LEASED`.
**Kette innerhalb einer Sitzung:** Schreibfehler auf `project_memory/.audit/hook_events.jsonl` (Sperre, Pfadlänge,
volle Platte) → jeder Bauer-Spawn dieses Ziels verweigert + Lease verbrannt.
**Schwere: hoch (blockierend für die Zielrunde, nicht für die zweite Hälfte).**
**Minimalfix:** den ganzen Rumpf von `_mirror_the_builder_start` ab `lines = …` in dasselbe `except Exception`
ziehen (bzw. den Aufruf in `handle_pre_tool_use` in `try/except BaseException: pass` klammern) — ein roter Test
dazu: Mutation B2 gegen einen Prozesslauf, der `rc == 0` zusichert.

### B2 — Die benannte Effort-Ausnahme (`office`-Ablagesockel, DEC-0047) ist nicht mehr fest: eine Auftrags-Bitte hebt sie
`team-kits/kernel/dispatch.py:2883` (die Effort-`max()` läuft **nach** dem Ausnahme-Zweig und kennt die Ausnahme
nicht als Decke), Zusicherung in `:2792` („unless the role's exception fixes one (the office filing floor,
DEC-0047)"), `team-kits/office-team/ladder.yaml:14` („So the pair STARTS on sonnet at low effort") und `:74` /
`dev-team/ladder.yaml:69` („`effort` (a fixed effort that replaces the pair)").

Gemessen gegen die **echte** `office-team/ladder.yaml` (Probe P1):
```
P1 plain filing lease : effort='low'  why='… class reading starts on pin … effort low: the exception fixes it'
P1 asked filing lease : effort='high' why='… class reading starts on pin … effort high: the order asks high'
```
`create-task --assigned-role records-clerk --effort high` hebt damit den Sockel, den DEC-0047 als „reines Lesen,
Doppelkontrolle" gesetzt hat. Die Deckenrechnung `ceiling = max(ladder["effort"].values())` (`:2882`) liest nur
`default`/`large`, nie die Ausnahmen — die xhigh-Kappung (DEC-0078) greift, die `low`-Ausnahme nicht.
**Schwere: mittel.** **Minimalfix:** entweder die Ausnahme als Decke führen (`ceiling = min(ceiling,
exception[EFFORT_KEY])`, wenn eine gesetzt ist) und den Test
`test_the_filing_pair_starts_on_its_pin_at_low_effort_and_still_climbs` um den Ask-Fall erweitern — oder, wenn das
Heben gewollt ist, die drei Kommentarstellen ändern und den Fall als benannte Zeile in DEC-0091 aufnehmen. So wie
es steht, behauptet der Kommentar Schutz, den der Code nicht baut.

### B3 — `covering_record` liest weniger als sein Docstring: ein **neuerer** Datensatz „overlapping" hebt einen älteren „disjoint" nicht auf
`team-kits/kernel/scopes.py:326-345` („The **NEWEST** record that measured `first` and `second` disjoint **AS THEY
STAND NOW**") gegen `:307` („NEWEST FIRST — … the newest run over a pair is the one that measured the orders as
they stand"). Der Code nimmt den neuesten Datensatz, **der „disjoint" sagt**, und überspringt jeden neueren, der
dasselbe Paar als überlappend gemessen hat; die Digest-Prüfung greift nicht, weil sich an den Aufträgen nichts
geändert hat — nur am Baum.

Gemessene Zeile (Probe P4c, zwei Datensätze über dasselbe Paar, Digests unverändert):
```
P4c records newest-first: ['…033421-beddb1d4.check.yaml', '…033420-2134b272.check.yaml']   (der neuere sagt OVERLAP)
P4c covering_record -> 2026-09-11T033420-2134b272.check.yaml                                (der ältere)
P4c second build lease -> {'TSK-0001': 'tasks/scope-checks/2026-09-11T033420-2134b272.check.yaml'}  → ERTEILT
```
**Begrenzt** ist das durch die Live-Überlappungsprüfung, und das habe ich gemessen (P4d, echter Dateikonflikt +
Datensatz, der „disjoint" sagt): `P4d second lease REFUSED by: TSK-0002 and TSK-0001 … both own src/shared/a.py`.
Die Verweigerung kommt also aus `_assert_no_running_lease_owns_the_same_file_locked`, nicht aus dem neuen
Struktur-Gate — das Struktur-Gate selbst lässt eine veraltete Messung durch.
**Schwere: mittel (Löcherliste, nicht rundenblockierend, weil die Live-Prüfung dieselbe Klasse fängt).**
**Minimalfix:** den **neuesten Datensatz nehmen, der das Paar überhaupt nennt** (`disjoint` *oder* `overlapping`),
und nur ihn befragen; roter Test = P4c.

### B4 — Das kitlose Vokabular kommt in umgekehrter Reihenfolge zurück
`team-kits/kernel/dispatch.py:206` — `"""(rungs low -> high, where they come from)…"""`. Gemessen:
```
kit-less answer: ('fable', 'opus', 'sonnet') from model_tiers.yaml
```
`model_tiers.yaml:49-51` listet die Referenzzeile `fable/opus/sonnet` — also **hoch → niedrig**. Heute folgenlos,
weil die kitlose Antwort nur auf Mitgliedschaft geprüft wird (`rung not in rungs`); die erste Stelle, die dieses
Tupel indiziert (ein `rungs.index(...)`-Vergleich wie in `ladder_for_order`), dreht die Ordnung stillschweigend um.
**Schwere: niedrig (latent).** **Minimalfix:** `_reference_rungs` in `EFFORT_LEVELS`-Manier explizit ordnen (oder
die Tabelle in `model_tiers.yaml` niedrig→hoch schreiben) — plus eine Zusicherung im kitlosen Test, die die
Ordnung liest.

### B5 — Der Stolperdraht auf „die Referenzzeile wird an ihrer EIGENSCHAFT erkannt" kann nicht rot werden
`team-kits/kernel/dispatch.py:233` („THE REFERENCE ROW IS FOUND BY ITS PROPERTY, **not by a provider name**");
`tools/test_light_kit.py` nennt die Schleife über `kit_dirs()` ausdrücklich „the tripwire on the property".

Gemessene Zeile (eigene Mutation N3b — Zeilenwahl hart auf `provider == "claude"` verdrahtet, Namensfilter auf `!=
"effort_field"`, für die heutige Tabelle also **identische** Sprossen):
```
"verdict": "GREEN"  —  49 passed in 21.76s   (tools/test_ladder.py + tools/test_light_kit.py)
```
Der genannte Stolperdraht misst nur, dass die Sprossen der Kits Teilmenge des Ergebnisses sind — das gilt für die
Eigenschafts- **und** für die Namensvariante, weil die Referenzzeile heute zufällig `claude:` heißt.
**Schwere: mittel (Regel 1/2: eine behauptete Eigenschaft ohne Test, der sie verletzen könnte).**
**Minimalfix:** `_reference_rungs` gegen eine **synthetische** Tabelle fahren, in der die Durchreich-Zeile unter
einem anderen Provider-Namen steht (und `claude:` eine übersetzende Zeile ist) — plus die Null-/Zwei-Zeilen-
Verweigerung.

### B6 — Zeile (a) des Checkpoints ist unbegrenzt, und der Spiegel kostet Sekunden pro Bauer-Spawn
`team-kits/kernel/dispatch.py:2941-2943` — `"; ".join(" + ".join(group) for group in sets)` ohne jede Kürzung;
`scopes.PATHS_SHOWN = 10` existiert für genau dieses Problem eine Datei weiter.

Gemessen (eigene Kostenproben, Store in der Größe dieses Repos: 130 offene Aufträge):
```
COST on 130 open orders / 400 files:  reflection_checkpoint 1.909 s (davon goal_partition 1.800 s)
files=3000 orders=10 -> reflection_checkpoint 0.57 s, line (a) length 174 chars
files=3000 orders=25 -> reflection_checkpoint 3.44 s, line (a) length 324 chars
```
Die Registrierung, gegen die das zu messen ist, steht in `team-kits/dev-team/settings/settings.json:104-110`
(`Agent|Task` → `_gate.py guard_agent_spawn.py gate_dispatch.py`) und nennt **kein** `timeout`; das Standardfenster
ist laut `tools/provider_observations.json` `hook_deadlines.no_timeout_key` bei ~600 s geklammert (längster
überlebender Lauf 560 s). Die 3,4 s sind also **kein** Durchlass-Risiko — aber der Aufwand wächst mit den Paaren
eines Ziels (O(n²)·Dateien), und Zeile (a) wandert ungekürzt in den Modellkontext jedes Bauer-Spawns.
**Schwere: niedrig.** **Minimalfix:** Zeile (a) nach `PATHS_SHOWN` Gruppen kürzen („… und N weitere Mengen"),
`goal_partition` auf die Aufträge des Ziels begrenzen (tut es bereits) und die Partition bei mehr als k offenen
Aufträgen als Zahl statt als Liste ausgeben.

---

## B. Prosa gegen Code (DEC-0088 (c)) — getrennt aufgeführt

| # | Stelle | Behauptung | Gemessener Stand |
|---|---|---|---|
| P1 | `team-kits/kernel/dispatch.py:2841` | `floor_why = "the exception fixes the start"` | Die Ausnahme ist nur noch Boden. Gemessen (P2): `rung='fable' why="fable: pin sonnet, **the exception fixes the start, the order asks fable**, 0 failed run(s), top fable"` — zwei Aussagen, die einander im selben Satz widersprechen. Fix: `"the exception sets the floor"`. |
| P2 | `team-kits/dev-team/ladder.yaml:69`, `office-team/ladder.yaml:74` | „`rung` (a fixed starting rung that replaces class and pin)" | Siehe P1/B2: ersetzt Klasse und Pin, ist aber gegen eine Auftrags-Bitte nicht mehr fest. |
| P3 | `team-kits/…/hooks/gate_dispatch.py:254` | „`additionalContext` — the one channel of **this event** that reaches the MODEL (`tools/provider_observations.json`, hook_output_channels)" | Der zitierte Datensatz misst ausschließlich **PostToolUse** (`hook_output_channels.measurement.method`: „ONE PostToolUse(Bash) hook …"; einziger Ergebnisschlüssel `post_tool_use`). Für PreToolUse steht dort nichts. Fix: entweder messen oder als Provider-Doku statt als eigene Messung zitieren. |
| P4 | `team-kits/kernel/dispatch.py:522` | „**the PM** has to have run `check-scopes` over the pair" | Der Code liest einen Datensatz, nicht einen Urheber. `check-scopes` steht nicht in `gate_write_scope._ORDERING_COMMANDS` (`:963` = `create-task`, `capture TSK`, `dispatch`), jede Rolle kann ihn erzeugen. Fix: „somebody has measured …" plus die Grenze benennen. |
| P5 | `team-kits/kernel/report.py:262`, `:294` | „The last `window` **leases** of this project" / `last %d lease(s)` | `_leased_orders` liefert **Aufträge**, nicht Leases; `leased_at` wird bei jeder Neuvergabe überschrieben, ein dreimal eskalierter Auftrag zählt einmal. Ein Projekt mit 3 Aufträgen und 9 Dispatches meldet dem Nutzer „last 3 lease(s)". Fix: „orders" schreiben oder Dispatches zählen. |
| P6 | `team-kits/kernel/report.py:255`/`:271` | „runs … **until it passed its run**" | Gemessen (P5): `_ran_to_done` ist ab **SUBMITTED** wahr (`DRAFT/READY/LEASED/IN_PROGRESS → False`, `SUBMITTED/DONE/VALIDATED → True`, `CANCELLED → False`). SUBMITTED heißt abgegeben, nicht bestanden. Fix: Wortwahl „handed back" oder Schwelle auf DONE. |
| P7 | `project_memory/staging/TSK-0135/protocol.md` §0 | „ein Auftrag, der nach einem FAIL einmal gestiegen ist, stiege beim nächsten Lease **doppelt** … Rig-Zeile M16 stellt genau diese Form wieder her" | M16 wird rot an einer **Feldzusicherung** (`assert dispatch.RUNG_KEY not in item` → „the lease wrote its answer under the ask's name") — nicht am Doppelaufstieg; auf den drei ausgelieferten Sprossen ist der Doppelaufstieg von `top` verdeckt. Ich habe ihn selbst gemessen: auf einer 6-Sprossen-Leiter liefert der gelieferte Stand `['r1','r2','r3','r4']`, mit M16 `['r1','r2','r4','r5']`. Der Grund der Zwei-Namen-Trennung stimmt also — er steht nur nirgends als Test. Fix: meine Probe P3 als Testzeile in `test_light_kit.py` übernehmen. |
| P8 | `dispatch.py:2941` | „this goal splits into N **measured-disjoint** sets" | Die Partition wird live gerechnet, nicht aus einem `check-scopes`-Datensatz gelesen. Ein PM, der „2 measured-disjoint sets" liest, hält die zweite Bau-Lease für erteilbar — sie wird ohne Datensatz verweigert. Fix: „splits into N disjoint sets (computed now; the second builder still needs a check-scopes record)". |

---

## C. Negativbefunde

**Gemessen und in Ordnung:**
- **AC-3 Ableitung.** Bitte hebt den Start, senkt nie: M1-Replay rot (`AssertionError: {'rung': 'sonnet', …}
  assert 'sonnet' == 'opus'`); Gegenrichtung (Architekt bittet `sonnet`, bleibt `fable`, „not above it") und
  `top`-Kappung sind in `test_light_kit` grün gemessen.
- **Eskalation ab dem Startpunkt des Auftrags:** genau eine Sprosse je FAIL, auf einer Leiter, die lang genug ist,
  um einen Doppelaufstieg zu zeigen — `['r1','r2','r3','r4']` (Probe P3).
- **Office-Decke:** `xhigh → high` gegen die **echte** `office-team/ladder.yaml` (Decke aus `max(default, large) =
  high`).
- **Vokabular-Verweigerung** bei `create_task` **und** beim Lease, über beide CLI-Wege (`create-task` und `capture
  TSK` gehen beide durch `dispatch.create_task`, `cli.py:1588`/`:1627`); kitlos gegen die Referenzzeile.
- **Struktur-Gate:** zweite Bau-Lease ohne Datensatz verweigert; mit veraltetem Digest verweigert (M8-Replay rot:
  `FAILED …::test_a_record_stops_covering_an_order_whose_scope_moved_since`); zwei Bauer unter zwei Zielen und eine
  QA-Lease daneben bleiben unberührt; kitloses Projekt ausdrücklich außerhalb und benannt.
- **Checkpoint:** vier Zeilen + Frage, als `hookSpecificOutput.additionalContext` vom **ausgelieferten** Hook als
  echtem Prozess, `rc 0`, auditiert; bei werfender Ableitung `HOOK rc=0` (B1-Replay).
- **Spiegelung byte-identisch ×3:** SHA256 `51667967173DE368…49D2`, Länge 33396 für alle drei `gate_dispatch.py` —
  deckt sich mit dem im Protokoll genannten Präfix.
- **Verteilungszeile:** Fenster und Archivhälfte sind belastbar — beide eigenen Mutationen rot
  (`DISTRIBUTION_WINDOW = 10 → 3`: RED; `_ran_to_done` `>` → `>=`: RED).
- **Nachgezogene Leser, je eine Mutation:** `test_board` (Eintrag entfernt → `FAILED
  …::test_no_kernel_writer_of_a_rendered_file_leaves_the_board_behind`), `test_schemas` (Abschnitt aus `make_brief`
  entfernt → `missing required field 'lease_distribution'`, 3 rot), `test_approvals_dispatch` (`node.level != 1` →
  `!= 9` → 2 rot), `test_report` (M17 → 1 rot), `test_ladder` (M16 → 1 rot). Alle fünf können weiterhin aus ihrem
  Grund scheitern; der Board-Eintrag hat beidseitigen Stolperdraht (`offenders` **und** `dead`).
- **Zwischenstempel:** `python tools/bump_kit_version.py` in meiner Kopie →
  `dev-team/office-team/research-team: unchanged (2026.09.11-1)` ×3.
- **Kein Repo-Schreibzugriff:** alle Mutationen restauriert, Kopie und Repo byte-gleich.

**Nicht gemessen (bewusst offen gelassen):**
- Die volle `tools/`-Suite (Gate 5 / DEC-0050 — nicht Sache des Prüfers); ich habe nur die berührten Dateien
  selektiv gefahren. `tools/test_model_ladder.py::test_no_shipped_kit_text_still_names_the_retired_user_gated_ladder`
  fiel in meiner Kopie mit `fatal: not a git repository` — **das ist ein Artefakt meiner Kopie ohne `.git`, kein
  Befund**; ich nehme das ausdrücklich zurück, nachdem ich die Fehlerzeile gelesen hatte.
- AC-12 „**no free-text justification field anywhere**": ich habe keinen strukturellen Test gefunden, der das
  misst, und keinen gebaut. Bleibt für die zweite Hälfte.
- Wachstum und Bereinigung von `tasks/scope-checks/`: jeder `check-scopes`-Lauf legt eine Datei an, nichts räumt
  auf, und `records()` liest bei jeder zweiten Bau-Lease alle. Nicht vermessen, nur gelesen.
- Kitlos + `update` auf eine Müll-Sprosse: `ladder_for_order` kehrt beim kitlosen Projekt vor der
  Vokabularprüfung zurück — nicht vermessen, weil die Bitte dort ohnehin unbenutzt bleibt.
- Die Textflächen, AC-2/4/5/6/7/8/10/11, Pilot-Rig und Rückschau-Regel — nicht Gegenstand der Hälfte.
- Office- und research-Kit als **laufende** Pilotprojekte (ich habe nur dev-team scaffolded und dessen
  `settings.json` gelesen); die Spiegelgleichheit der drei Hooks ist per Byte gemessen, ihr Verhalten nur für
  dev-team.

---

## D. Urteil

**CONTINUE.**

Der Kernel-Vertrag (Zwei-Namen-Trennung, `max()` mit Boden und Decke, Eskalation ab dem Startpunkt), das
Struktur-Gate und der Checkpoint stehen; die zweite Hälfte baut nicht auf Sand. Kein Befund kippt eine
Entscheidung, auf der die Texte, die Einstiegsdatei und die Experiment-Arme aufsetzen.

Einordnung der Befunde für die Phasen 2–6:

- **B1 blockiert die Zielrunde** (nicht die Hälfte): die Kette — Audit-Schreibfehler → `rc 2` → Bauer-Spawn
  verweigert bei verbranntem Lease-Claim — läuft innerhalb einer Sitzung durch und widerspricht DEC-0092 (3) und dem
  eigenen Docstring. Vor der Prüferrunde am Ziel geschlossen, mit rotem Test (Mutation B2).
- **B2** (Ablagesockel) und **B5** (Stolperdraht ohne Rotwerdefähigkeit) gehören in Phase 2 mit Fix **oder** mit
  geänderter Prosa — in beiden Fällen mit einer Testzeile.
- **B3** ist ein **benannter Rest für die Löcherliste** (`docs/POST_V2_WISHLIST.md`), mit Mechanismus statt
  Beispiel: *„`scopes.covering_record` beantwortet ein Paar aus dem neuesten Datensatz, der es disjunkt nennt, statt
  aus dem neuesten, der es überhaupt nennt; ein später gemessener Überlappungsbefund hebt eine ältere Freigabe nicht
  auf. Begrenzt durch die Live-Überlappungsprüfung in `_assert_no_running_lease_owns_the_same_file_locked`, die
  dieselbe Datei-Klasse fängt (gemessen P4d)."*
- **B4, B6 und P1–P8** sind Nacharbeit in Phase 2, ohne eigene Runde.
