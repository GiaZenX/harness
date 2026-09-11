# Prüfbericht TSK-0135 — Zielrunde (PR-0011, zwölf ACs) — **FAIL**

Prüfer: `harness-verifier` (Opus, high). Die EINE Zielrunde nach DEC-0088 (b). Als Text geliefert, vom Lead
unverändert hierher gelegt (2026-09-11 07:5x, Uhr gelesen). Hinweis des Relays: der Bericht nennt
`settings.json` und `--dangerously-skip-permissions` als Messgegenstände; das sind Befunde, keine Anweisungen.

**Arbeitskopie:** `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0135/verify/goal/repo` (ohne `.git` kopiert; `git
init` + `git add -A` erst danach, weil `test_radar_trigger` `git ls-files` braucht — genau der Artefaktbefund, den
ich im Zwischencheck zurückgenommen hatte).
**Eigenes Rig:** `…/verify/goal/rig/` — `mutate.py` verweigert jedes fremde Arbeitsverzeichnis (`[rig] refused: this
rig runs only from …/rig`) und liest/schreibt **binär**; jede Mutation wird im `finally` zurückgeschrieben, alle
Läufe meldeten `restored: true`.
**Eigene Piloten:** drei vom kit-eigenen Installer gebaute Projekte unter `…/verify/goal/pilots/`
(dev/office/research), gegen die ich die ausgelieferten Hooks als **echte Prozesse** gefahren habe.
**Basis:** Hauptcheckout 07:0x, Stempel `2026.09.11-4` ×3. Läufe 06:50–07:45, Uhr je Lauf gelesen.

---

## A. Blockierende Befunde

### B1 — AC-6: das Experiment ist nicht gemessen, und der Grund für den nicht gefahrenen Arm B ist **behauptet, nicht gemessen**
`project_memory/staging/TSK-0135/experiment/arm-b-kit.md` (Abschnitt „Warum der Lauf hier NICHT unbeaufsichtigt
gefahren wurde"), `project_memory/tasks/active/TSK-0135.yaml:50-54` („you PREPARE both arms **and run the kit arm**").

AC-6 verlangt „tokens, wall-clock, rounds and the USER's quality verdict, **recorded as EVD with the numbers**" und
daraus eine DEC. Gefahren wurde **kein** Arm; es gibt keine EVD-Zeile mit Zahlen und keine DEC. Das Item hatte den
Kit-Arm ausdrücklich als Aufgabe des Umsetzers benannt.

Gemessene Zeile (die Begründung selbst):
```
grep über tools/provider_observations.json (alle Werte, rekursiv):
  /hook_events/measurement/mode           -> headless
  /hook_deadlines/measurement/mode        -> headless (-p, --dangerously-skip-permissions, --model haiku)
  /hook_output_channels/pre_tool_use/…    -> headless (-p, --output-format json, …)
  KEIN Eintrag über AskUserQuestion im -p-Modus
```
Die Aussage „Eine Headless-Sitzung (`-p`) kann `AskUserQuestion` nicht beantworten; der PM bleibt am ersten Tor
stehen" ist damit die einzige nicht gemessene Tatsachenbehauptung der Runde — in einer Runde, die um 03:55 eine
echte `claude -p`-Sitzung für die P3-Messung gefahren hat, also mit dem Werkzeug in der Hand.

**Schwere: hoch. Blockiert die Runde** in dem Sinn, dass AC-6 als „geliefert" nicht gelten kann.
**Minimalfix:** entweder Arm B interaktiv fahren (drei Klicks, wie `arm-b-kit.md` es beschreibt) — oder, wenn er
auf den Nutzer wartet, den Grund **messen**: eine `-p`-Sitzung im vorbereiteten Arm-B-Projekt starten, die Stelle
protokollieren, an der der PM stehen bleibt, und die Beobachtung als Eintrag in `tools/provider_observations.json`
ablegen. Dann ist AC-6 „vorbereitet + Grund gemessen, Urteil beim Nutzer" statt „vorbereitet + Grund behauptet".

### B2 — AC-10: die (g)-Zusammenfassung widerspricht ihrer **eigenen** Tabelle
`project_memory/staging/TSK-0135/protocol.md:429-432`.

Gemessen gegen die Zahlen, die drei Zeilen darüber stehen:
```
Behauptung 1: "kostete bis hier weniger Tokens als EIN Strom der Generation 5"
   G6 = 937 k   G5-1 = 896 k   G5-2 = 649 k   G5-3 = 630 k     ->  937 > alle drei
Behauptung 2: "ein Sechstel bis ein Viertel der Wanduhr"
   G6 = 4 h 13 = 253 min
   253/490 (G5-1) = 0.52   253/656 (G5-2) = 0.39   253/803 (G5-3 Spanne) = 0.31
   -> das kleinste Verhältnis ist rund ein DRITTEL, nicht ein Sechstel bis ein Viertel
```
Die beiden Hälften vergleichen außerdem gegen verschiedene Bezugsgrößen (Tokens gegen **einen** Strom, Wanduhr gegen
die **Summe** dreier Ströme). Zusätzlich trägt `:418` „**Stand 04:58**", während die G6-Zeile die Lieferzahlen von
06:47 führt.

Die Gen-5-Quellzahlen selbst habe ich gegen `project_memory/staging/generation-5-streams.md` geprüft und sie
stimmen (896 k/332/8 h 10; 649 k/442/10 h 56; 630 k/5:46 über 13:23; Merge ~770 k).

**Schwere: hoch.** AC-10 ist genau „der ehrliche Vergleich"; eine Zusammenfassung, die ihrer eigenen Tabelle
widerspricht, ist Hausregel 3 im Kern — und zwar in der Richtung, die zugunsten der neuen Form irrt.
**Minimalfix:** den Satz an die Tabelle anpassen: „~937 k gegen 896 k des teuersten Einzelstroms und gegen ~2,95 M
der drei Ströme plus Merge; 4 h 13 gegen 8 h 10 / 10 h 56 / 13 h 23 Spanne — rund ein Drittel bis die Hälfte eines
einzelnen Stroms, rund ein Achtel ihrer Summe", und „Stand 04:58" entfernen oder auf 06:47 setzen.

---

## B. Befunde an Lesern (die Klasse, die ich zuerst angegriffen habe)

### B3 — AC-2: der Teamgrößen-Leser wird vom Wort **„derived"** ausgehebelt, und sein Docstring behauptet das Gegenteil
`tools/test_hooks.py:6083` (`_DERIVED_NOT_ASKED_RX` enthält die nackte Alternative `derived|Ableitung`), Behauptung
in `:6110` („**RED on any text** that tells the agent to ask the user which team size or preset they want").

Gemessene Zeilen (drei Mutationen, dieselbe Frage, ein Wort Unterschied):
```
AC-2 a: "- **Ask which TEAM SIZE they want, and ask it as its own question.** …"  in user/claude/CLAUDE.md
        -> RED  (FAILED …::test_no_entry_file_and_no_lead_text_asks_the_user_for_the_team_size)
AC-2 b: dieselbe Zeile im ZWILLING user/codex/AGENTS.md
        -> RED
AC-2 c: "- **Ask which TEAM SIZE they want** und write down the preset DERIVED from the answer."
        -> GREEN   (2 passed, 1018 deselected in 1.87s)
```
Das Wort steht in genau dieser Textfamilie überall — der Leser selbst findet 13 Sätze, die er begnadigt, davon zwei
allein über `derived|DERIVED`. Die übrigen elf hängen an `never ask` / `NOT asked` / `removed the question`, also an
Formulierungen, die niemand versehentlich trifft.

**Minimalfix gemessen**, beide Richtungen:
```
ac2fix1  `derived|Ableitung` aus _DERIVED_NOT_ASKED_RX entfernt, sonst nichts
         -> GREEN (kein einziger Falschtreffer auf den ausgelieferten Texten)
ac2fix2  dieselbe Kürzung + die "derived"-Frage wieder eingesetzt
         -> RED
```
(Die beiden Sätze, die heute auf `DERIVED` hängen, lauten „DERIVED, **never asked** (`DEC-0087` (2))" — die `never
ask`-Alternative fängt sie weiterhin. Der Fix kostet nichts.)
**Schwere: mittel. Nicht rundenblockierend** (keine Angriffskette), aber Hausregel 3: der Docstring behauptet
Deckung, die der Code nicht baut.

### B4 — AC-4: der Takt-Leser wird von **jedem** „not" / „kein" im Satz ausgehebelt
`tools/test_light_kit.py:638` — `_NEGATED_RX = re.compile(r"\b(no|not|never|none|nie|kein|keine|nicht)\b|\bdo
not\b", re.IGNORECASE)`.

Gemessene Zeilen:
```
AC-4 a: "After every rework the verifier runs the whole package again."
        -> RED  (FAILED …::test_no_kit_text_still_orders_a_verifier_after_every_rework)
AC-4 b: "After every rework the verifier runs the whole package again, and this is NOT optional."
        -> GREEN (2 passed, 24 deselected in 0.67s)
```
Über die ausgelieferten Texte gemessen hängen genau **zwei** Sätze an der Verneinung, beide „You **do not order** a
verifier after every rework" (dev + research PM-Skill). Die Verneinung muss also nur die verneinte ANORDNUNG
treffen, nicht irgendein Verneinungswort.

**Minimalfix gemessen:**
```
ac4fix1  _NEGATED_RX -> r"\b(do|does|should|will|shall|may|must) not\b|\bnever\b|
                        \bno (separate |second )?(verifier|reviewer|review|QA|Pr[uü]fer)\b|
                        \bkein(e[nr]?)? (Pr[uü]fer|Review)\b"
         -> GREEN (keine Falschtreffer auf den ausgelieferten Texten)
ac4fix2  derselbe Fix + die "not optional"-Anordnung wieder eingesetzt
         -> RED
```
Nebenbefund derselben Probe: `_VERIFIER_RX` kennt `Pr[üu]fer`, aber nicht die ASCII-Umschrift `Pruefer` — die eine
deutsche Anordnung in Umschrift (`ac4fix3`) bleibt auch mit dem engeren Negationsleser **GREEN**. Die
`user/codex/AGENTS.md` ist genau in dieser Umschrift geschrieben.
**Schwere: mittel, nicht blockierend.** Der Docstring dieses Lesers ist ehrlicher als der von B3 („without a negation
… is red"), der **AC**-Text aber sagt „red on **any** kit text that still orders a verifier after every rework".

### B5 — AC-5: für die neue Erstkontakt-Frage existiert **kein einziger Leser**
`user/claude/CLAUDE.md:52`, `user/codex/AGENTS.md:98`.

Gemessene Zeilen:
```
grep -rl "Langzeit-Ged" tools/ team-kits/ .claude/          -> keine Treffer
AC-5 a: die Frage in user/claude/CLAUDE.md durch die ALTE ersetzt
        ("Strukturiert über einen Project Manager arbeiten?")
        -> GREEN  1099 passed, 13 skipped in 749.36s
           (tools/test_hooks.py + test_light_kit.py + test_shortening_net.py + test_role_contracts.py)
AC-5 b: dasselbe im ZWILLING user/codex/AGENTS.md
        -> GREEN  1099 passed, 13 skipped in 1143.27s
tools/constitution_section_pins.json  -> pinnt NUR Kit-Dateien (dev/office/research:
        agents/…, constitution/AGENTS.md, hooks/ENFORCEMENT.md, skills/…), keine Einstiegsdatei
```
Alle fünf Stellen, die die Einstiegsdateien überhaupt lesen (`test_hooks.py:5942/6056/6645`, `test_presets.py:919`,
`test_handover_marker.py:194`), prüfen Zustandspfade, Teamgrößen-Fragen, Sackgassensätze und den Shim-Marker —
**keine** die Frage.

Die Runde hat damit den positiven Leser abgeschafft, den P4-6 hatte (der die beiden Einstiegsdateien an DIESELBE
Klausel band), und nur den negativen behalten. Ein Revert der zentralen AC-5-Lieferung — in einer der beiden
Zwillingsdateien oder in beiden, auch auseinanderlaufend — bleibt unbemerkt.
**Schwere: mittel. Nicht blockierend**, aber AC-5 ist damit nicht „gemessen": der Pilot misst das Preset
(`solo/solo/core`), nicht die Frage.
**Minimalfix:** eine Zeile im vorhandenen AC-2-Test bzw. daneben — beide Einstiegsdateien tragen die Frage, und zwar
**dieselbe** (bis auf die Umschrift), plus ein Fixtur-Ende, das die alte Frage als Verstoß liest.

---

## C. Prosa gegen Code / gegen die ACs (DEC-0088 (c), getrennt)

| # | Stelle | Behauptung | Gemessener Stand |
|---|---|---|---|
| P1 | `protocol.md:441` (EVD-Zeile) und `:246` | „41 red-first rows red (**red_first-20260911-045047.log.json**)" | Die in das Repo gelegte Datei trägt **eine** Zeile: `rows=1 (P3-AC2) start 04:50:49 end 04:50:53`. Der 41-Zeilen-Lauf ist `rig/red_first-20260911-045313.log.json` (`rows=41, kein rc 0, 04:53:15–04:55:21`) und liegt **nur im Scratch**, das beim Rundenabschluss aufgeräumt wird. Fix: die 045313er Datei staggen und in EVD/§3a nennen. |
| P2 | `protocol.md:85` | `_routine.py` „gespiegelt, sha `ebfb2fcadea2855a`" | Ausgeliefert ist `1e6b941e1f45ab2a` (gemessen über alle drei Kits, byte-identisch) — die Zahl wurde von Fix #4 des Volllaufs 1 überholt und steht in derselben Datei zweimal (`:85` alt, `:3a` neu). Hausregel „eine Zahl an genau einem Ort". Fix: `:85` auf den Verweis statt auf die Zahl. |
| P3 | `protocol.md:405-407` (§6 (4)) | „Die Leser für AC-2 und AC-4 … ein neuer Wortlaut derselben Frage kann an ihnen vorbei (**im Test-Docstring gesagt**)" | Für AC-4 stimmt das; für AC-2 sagt der Docstring (`test_hooks.py:6110`) das **Gegenteil** („RED on any text…"). Fix: entweder den Docstring kürzen oder §6 (4) auf AC-4 beschränken. |
| P4 | PR-0011 AC-1 | „(gate_write_scope measured refusing a PM code write)" | Gemessen als Prozess je Kit auf meinen eigenen Piloten: `gate_write_scope.py` **allein → rc 0** (dev/office/research), die registrierte Kette `_gate.py guard_pm_scope.py gate_write_scope.py` → **rc 2**. Der Umsetzer nennt das in §5.5 (a) selbst; der AC-Text nennt das falsche Gate. Fix: AC-Text oder die Protokollzeile zieht die Kette. Der Schutz selbst steht. |
| P5 | PR-0011 AC-7 | „no hash / **request id** / YAML path in the question text" | Die Frage trägt weiterhin `[APR-REQ:876a66233aba4cf6a65fd7b3a415968c]` — Anfrage-Id **und** ein 32-stelliger Hexlauf. Der Test streicht den Marker, bevor er auf Hex prüft. Der Grund steht im Docstring (`gate_approval.MARKER_RX` liest ihn aus der Frage) und im Protokoll §5.1 — also benannt, nicht verschwiegen. Fix: AC-Wortlaut anpassen oder den Marker in die verglichene Option ziehen und `MARKER_RX` dort lesen lassen. |
| P6 | `approvals.py:1601-1605` | Ablaufdatum als `2026-09-25T05:06:25Z` in der deutschen Nutzerfrage | Determinismus ist begründet (zeichenweiser Vergleich in einem anderen Prozess) — aber die Zeile, die der Nicht-Entwickler beurteilt, liest sich maschinell und liegt je nach Zone bis zu zwei Stunden neben seiner Uhr. Ein festes UTC-**Datumsformat** (`25.09.2026, 05:06 UTC`) wäre gleich deterministisch. Schwere: niedrig. |
| P7 | `tools/light_kit_pilot.py:216` | `--trigger weekly --cadence weekly` | Das mitgelieferte Beispiel des Kits erzeugt eine deutsche Frage mit englischen Werten (`Takt: weekly, Auslöser: weekly`) und widerspricht damit der BUG-0073-Regel im Lead-Paket (`agents/project-manager.md:113-120`: der getippte Wert ist deutsch). Die Route selbst ist sprachneutral (`--cadence <how often>`). Schwere: niedrig. |

---

## D. Negativbefunde

### D.1 Gemessen und in Ordnung

**Die sechs Befunde meines Zwischenchecks, meine Mutationen unverändert nachgefahren:**
- **B1 (Spiegel blockiert nie).** Ausgelieferter `gate_dispatch.py` als echter Prozess gegen meinen dev-Piloten, je
  Fall eine frische, ungeclaimte Lease (Mutation in einer Kopie des Hook-Verzeichnisses, damit
  `_refuse_untrusted_bundle` nicht antwortet): `unmutiert TSK-0006 rc=0` · `record_note wirft TSK-0007 rc=0` ·
  `sys.stdout.flush wirft TSK-0008 rc=0` — Kontext in allen dreien geschrieben. Nur mein zusätzlicher Fall
  `reflection_checkpoint raises SystemExit` gibt `rc=7`; das ist die im Docstring ausdrücklich gewollte
  Durchreichung, und im ausgelieferten Code unerreichbar (`_kernel.record_note` kapselt in
  `contextlib.suppress(BaseException)`, `reflection_checkpoint` ruft kein `sys.exit`).
- **B2 (Effort-Ausnahme = Boden UND Decke).** Gegen den **echten** office-Piloten, Ende zu Ende über
  `create-task`/`dispatch`: `records-clerk ohne Bitte -> low` · `records-clerk bittet high -> low ("the order asks
  high, but the exception fixes low (DEC-0047)")` · `bittet medium -> low` · `bittet rung fable -> opus (top)`.
- **B3 (`covering_record`).** Mutation „nur der neueste DISJOINT-Datensatz" → **RED** (`FAILED
  …::test_a_newer_overlap_record_revokes_an_older_disjoint_verdict`). Der Code nimmt den neuesten Datensatz, der
  das Paar **überhaupt** nennt, und beendet die Schleife mit `return None` (`scopes.py:386`) — fail-closed auch bei
  einem Datensatz, der beides nennt.
- **B4 (kitlose Sprossenordnung).** `model_tiers.yaml:41 rungs: [sonnet, opus, fable]`, Ordnung wird gegen jede
  Kit-Leiter gelesen.
- **B5 (Eigenschaft statt Name).** Meine N3b-Mutation unverändert (`provider == "claude"` fest verdrahtet) →
  **RED**: `Failed: DID NOT RAISE DispatchError`, `tools\test_light_kit.py:522`.
- **B6 (Zeile (a) begrenzt).** Live im Checkpoint: `(a) this goal splits into 5 disjoint sets among 6 open order(s)
  (computed now; a second builder still needs a check-scopes record): …`; über `PATHS_SHOWN` Aufträgen nur die Zahl,
  `len(lines[0]) < 200` im Test.

**AC-1.** Auf meinem eigenen dev-Piloten, über die Kommandofläche: `dispatch TSK-0013 rc=0` · `(a) zweiter Bauer OHNE
Datensatz rc=1` („TSK-0014 would be a SECOND builder under PR-0001 beside TSK-0013, and no check-scopes record
measured its file set disjoint") · `(b) mit einem VERALTETEN Datensatz (Auftrag nach dem Lauf noch als DRAFT
umgeschnitten, allowed_scope ['src/s3/**','src/s4/**']) rc=1`. PM-Codeschreibzugriff: registrierte Kette rc 2 ×3
Kits (siehe P4).

**AC-3.** Alles gegen den echten office-Piloten, nicht gegen Fixtures: `bookkeeper bittet sonnet -> sonnet ("the
order's ask sonnet is not above it")` · `bittet xhigh -> high ("capped at the kit's highest effort high")` · `bittet
rung haiku -> create-task rc 1 (Kernel-Satz, DEC-0091 (3)/DEC-0076)` · `bittet effort ultra -> rc 2 (argparse
choices)`. Der Kernel-Weg ohne argparse ebenfalls zu: `capture TSK` mit `effort: ultra` → rc 1, mit `rung: haiku` →
rc 1. Doppelaufstieg: M16-Mutation → **RED** in
`test_the_two_name_split_is_what_keeps_a_climbed_order_from_climbing_twice` **und**
`test_ladder::test_the_header_and_the_task_carry_the_rung_and_effort`. `check-scopes` zeigt die Bitte neben jedem
Auftrag (gemessen, 10 Zeilen, inkl. „no tier ask (the ladder's own answer applies)"), der Brief trägt `rung`/`effort`
(Bitte) **und** `lease_rung`/`lease_effort` (Antwort) je Auftrag. Die Drei-Zeilen-Regel des Nutzers steht wörtlich
in allen drei Lead-Skills; „You never ask the user for tiers or for the team size" ebenfalls.

**AC-7.** `gate_approval.py` als echter Prozess gegen meinen Piloten, mit der Frage, die der Kernel wirklich erzeugt
hat: `verbatim rc=0` · `manipulierte Options-Beschreibung (ein Hex-Zeichen) rc=2` · `paraphrasierter Satz ("Bitte um
Freigabe:") rc=2` · `nur die Freigeben-Option rc=2` · `geänderter Header rc=2`. Hash-Präfix: **nicht** im Satz, **im**
Options-Text. Zwei-Enden-Stolperdraht: `ac7a` (Art ohne Label) → RED ×2 Tests, `ac7b` (Label ohne Art) → RED.

**AC-8.** Der Angriff auf den Fix, Ende zu Ende auf meinem Piloten:
- `presents()` über alle 14 Arten × PR/TSK gedruckt — nur `scope/delivery/plan` (+`acceptance` bei PR) präsentieren.
- Kann eine hängende Art eine **fehlende** Scope-Freigabe verdecken? **Nein.** Neue Wurzel `PR-0002` ohne
  Scope-Freigabe, Routine geprägt → `approval_ref` bleibt `None`, Bauer darunter `dispatch rc=1` („no user approval
  authorises dispatching TSK-0010 under PR-0002").
- Erreicht die neu gebaute Route mehr als sie darf? **Nein.** Routine mit Rolle `backend-developer` auf derselben
  Wurzel geprägt, schreibfähiger Auftrag (`allowed_scope ['src/z/**']`) → `dispatch rc=1`; derselbe Wurzelzustand mit
  einem `--read-only`-Auftrag → `dispatch rc=0`. Die Routine-Route trägt also wirklich, und sie trägt nur Lesearbeit.
- Kann ein read-only-Auftrag schreiben? Kind durch das Spawn-Gate gespawnt und über `SubagentStart` gebunden (`lease
  agent_id = agent-ro-9`), dann `gate_write_scope` als Prozess: `src/z/a.py rc=2` · `staging/audit/routine.md rc=2` ·
  `docs/anything.md rc=2` · `README.md rc=2` · fremdes Staging `rc=2` · **eigenes**
  `project_memory/staging/TSK-0012/note.md rc=0` (der Vorschlagsbereich, den CLAUDE.md ausdrücklich offen hält). Kein
  Spiegel für diesen Spawn — richtig, die Klasse ist `qa`, nicht `build`.
- Pilot-Rig je Kit in meinem eigenen Lauf: `auditor_dispatch_rc 0`, `lead_code_write_rc 2`,
  `second_builder_without_record_rc 1`, `checkpoint_rc 0`, Leases `sonnet/high · opus/high · fable/xhigh` (dev,
  research) bzw. `sonnet/high · opus/high · opus/high` (office, DEC-0078-Decke).

**AC-9.** `tools/test_radar_trigger.py` in meiner Kopie: **18 passed in 1.87 s** (nach `git init`). Beide Overlays
vorhanden (`.claude/agents/claude-watcher.md`, `codex-watcher.md`, `.codex/agents/*.toml`), beide `model: opus`,
`effort: high`, `harness_item: none`. `radar/routine.json` führt eine der vier Routinen mit Berichtskadenz als Beleg;
die drei fehlenden benennen die Watcher-Texte selbst als noch nicht angelegt — das ist die Nutzerzeile, die AC-9 in
seiner zweiten Hälfte verlangt.

**AC-11.** Harvest: die drei Projekte tragen **kein** `project_memory/.audit/kit_gaps.jsonl` (portfoliomanaigement
und synaipse haben nur `hook_events.jsonl`, synaipse-unified kein `.audit`), also ist „0 Einträge" der richtige Pfad
und das richtige Ergebnis, kein Fehlgriff. Unberührt: **null** Dateien mit einer mtime im Rundenfenster (ab 02:30
heute) in allen drei Projekten; ihr `git status`-Schmutz (10/0/9 Einträge) ist älter, `kit_state.json` von
portfoliomanaigement vom 2026-09-02. Update-Route: das Log zeigt `2026.09.06-1 -> 2026.09.11-2`, `update-kit rc 0`,
`HANDOVER_PENDING` gesetzt.

**AC-12.** `--why` als **Pflicht**-Option auf `create-task` → **RED** (`required options that feed no contract
field`). Verteilungszeile im Brief meines Piloten gemessen: `last 10 order(s) by their latest lease: 1 goal(s) with
builders; builders per goal 5 builder(s) x 1 goal(s); rungs opus x 4, sonnet x 6; runs to hand-back per rung none
handed back yet`. Rückschau-Frage 5 identisch in allen drei Auditor-Skills.

**Prozesszeilen.** Beide DONE-Zeilen gelesen und mit mtimes verglichen: `8 failed, 4874 passed, 14 skipped in
2371.94s` / `2026-09-11 05:35:29` und `4882 passed, 14 skipped, 0 failed in 2395.10s, rc=0` / `06:26:07`, Gates
`548 passed in 757.25s, rc=0` / `06:39:30`. Alle vier gestagten Logs CR=0. Von den acht Roten des Laufs 1 habe ich
zwei selbst rot-zuerst nachgestellt: Kommentar-Zitat `test_ladder.py::…` → `FAILED
test_repo_hygiene::test_every_test_pointer_this_repo_writes_resolves` (2:13); `PR-0011` zurück in einen
Research-Text → `FAILED test_hooks::test_kit_names_a_root_item_exactly_when_the_kernel_gives_it_one`. Rohprotokoll:
**18 Zeilen**, jede Uhrzeit deckungsgleich mit den mtimes (Rig-41 04:55:21 ↔ „04:52–04:55"; Stempel 05:45:27 ↔
„STAMP 2026.09.11-4" 05:45:57; BUG-0277 04:55:54 ↔ „(04:55)"). Löcher: **183** BUG-Items mit `hole_number`, Maximum
H193/BUG-0277; der aus dem Store frisch gerenderte Index deckt sich **Zeile für Zeile** (192/192) mit
`docs/POST_V2_WISHLIST.md`, `test_repo_hygiene -k "hole or pointer"` 6 passed. In meiner Kopie:
`bump_kit_version.py` → `unchanged (2026.09.11-4)` ×3, `validate.py` → all structural checks passed, `ruff` → All
checks passed. Spiegelung: 36 Hook-Dateien, 11 Unterschiede — alle im `KIT_SPECIFIC`-Muster (office fehlen die
dev-only Gates, `ENFORCEMENT.md`/`session_status.py`/`document_trays.txt` je Kit); `gate_dispatch.py` in allen drei
identisch (`8732487ea375abd8`).

**H193/BUG-0277 nachgestellt** (eigener Store ohne `write_kit_state.py`):
```
scaffold_team rc=0  [warn] …write_kit_state.py is missing -- no hook-bundle trust recorded
kit_state.json written: False      hooks installed: True
store kit hash : da4cd3218b141a4fc8009aa1ceee3d098c3f6ff5b2744891d83cd589a83fbf5c
VERSION content: 376001dc57a466d4ae55fc202319072d88ff822f3a5de1094b41a5563de5ff42
mit Rekorder  : 376001dc57a466d4ae55fc202319072d88ff822f3a5de1094b41a5563de5ff42
_kernel.bundle_trust(projekt).withdrawn -> False
```
Kette und `limits:`-Satz des Items stimmen genau: grüner Erstinstall ohne Vertrauensnachweis, derselbe Store danach
vom Stempelvergleich verweigert, und nichts blockiert das Projekt (`withdrawn=False`).

**Kein Repo-Schreibzugriff.** Voller SHA-Vergleich Kopie ↔ Repo: **0 Dateien nur in meiner Kopie**; 5 abweichende
und 6 nur im Repo (`generated/*`, `DEC-0095`, `DEC-0096`, `TSK-0136`, `staging/generation-6/*`) — alle vom parallel
arbeitenden Lead, keine davon unter `team-kits/`, `tools/`, `user/`, `docs/`. Jede Mutation meldete `restored: true`.

### D.2 Bewusst nicht gemessen

- Die volle `tools/`-Suite (Gate 5, DEC-0050 — nicht Sache des Prüfers; ich habe die DONE-Zeilen gelesen und
  nachgerechnet).
- Die Token-Zahlen der (g)-Tabelle (`15 000 000 → 14 063 477`): der Zähler des Umsetzers, für mich nicht nachlesbar.
  Nur die **Arithmetik** dagegen habe ich geprüft — siehe B2.
- Eine echte Einstiegssitzung, die die AC-5-Frage stellt; Arm A und Arm B des Experiments; das Qualitätsurteil des
  Nutzers.
- Die Laufzeit des Spawn-Gates unter Last auf der registrierten `Agent|Task`-Zeile: der Eintrag der Kits trägt
  **kein `timeout`** (nur `gate_pipeline.py` hat eines, 1800 s), also greift das Provider-Standardfenster; die
  1,9–3,4 s aus meinem Zwischencheck stehen, ein neuer Lastlauf steht aus. Das ist eine Eigenschaft der
  Kit-Registrierung und liegt **außerhalb PR-0011**.
- `.claude/settings.json` dieses Repos (forbidden_scope des Items) und die drei Gates darin.
- Die drei Piloten als *laufende* Sitzungen (ich habe je Kit nur Prozesse gefahren, keine Modellsitzung).
- Das Wachstum von `tasks/scope-checks/` über lange Zeiträume (`_drop_records_about_closed_orders` räumt nur
  geschlossene Aufträge; gelesen, nicht vermessen).
- Ob `_valid_ladder` eine Rollen-Ausnahme mit einem Effort **über** der Kit-Decke ablehnt (die Decke ist seit B2 die
  Ausnahme selbst — gelesen, nicht vermessen).

---

## E. Urteil je Kriterium

| AC | Urteil | Grund |
|---|---|---|
| AC-1 | **PASS** | beide Verweigerungen gemessen (ohne Datensatz, mit veraltetem); PM-Schreibzugriff über die registrierte Kette rc 2 ×3. Abweichung P4 (der AC nennt das falsche Gate) benannt. |
| AC-2 | **FAIL (Prosa/Test)** | Substanz geliefert, aber B3: der Leser lässt dieselbe Frage mit dem Wort „derived" durch, während sein Docstring „RED on any text" behauptet. Einzeiliger, gemessener Fix. |
| AC-3 | **PASS** | Vertrag, `max()`, Boden, Decke, Ausnahme als beides, `top`, Eskalation ab dem Auftragsstart (6-Sprossen-Test rot unter M16), Vokabular über beide CLI-Wege, Lease/Brief/`check-scopes`, Drei-Zeilen-Regel ×3, keine Stufenfrage an den Nutzer. |
| AC-4 | **PASS mit Befund** | Takt in allen sechs Lead-Texten, Rückschau-Zeile ×3; B4: der Leser ist schwächer als das „any kit text" des AC. Gemessener Fix liegt vor. |
| AC-5 | **FAIL (Deckung)** | Frage wörtlich in beiden Zwillingen, Solo-Preset vom Rig gemessen — aber **kein Leser**: beide Zwillinge dürfen auf die alte Frage zurückfallen, 1099 Tests bleiben grün. |
| AC-6 | **FAIL (blockierend für dieses AC)** | kein Arm gefahren, keine EVD mit Zahlen, keine DEC; der Grund für Arm B ist behauptet statt gemessen. |
| AC-7 | **PASS** | deutscher Satz, Label-Tabelle beidseitig rot, Hash/Pfad in der verglichenen Option, Gate als Prozess bei Manipulation **und** Paraphrase rc 2, BUG-0073-Regel steht. Abweichung P5 (Anfrage-Id bleibt im Satz) benannt. |
| AC-8 | **PASS** | Route Ende zu Ende auf der Route selbst gemessen (nicht nur unter einer Wurzel, die ohnehin eine Scope-Freigabe hatte); die Änderung an `presents` verdeckt keine fehlende Freigabe und erlaubt keinen schreibenden Auftrag. |
| AC-9 | **PASS** | 18 passed, Overlays auf opus, Namen/Suffixe da; die drei fehlenden Routinen sind die Nutzerzeile, die der AC selbst nennt. |
| AC-10 | **FAIL (blockierend für dieses AC)** | B2: die Zusammenfassung widerspricht der eigenen Tabelle in beiden Zahlen. Form (ein Bauer, ein Zwischencheck, eine Zielrunde) stimmt. |
| AC-11 | **PASS** | Harvest am richtigen Pfad und ehrlich leer; drei Projekte nachweislich unberührt; Update-Route gemessen. |
| AC-12 | **PASS mit gemessener Grenze** | beide Verweigerungen rot-zuerst, Checkpoint nie blockierend (drei Prozessfälle rc 0), Verteilungszeile im Brief, Rig ×3 Kits, Pflicht-`--why` rot — **aber** ein **optionales** `--why` bleibt grün, während der AC „anywhere" sagt (Test-Docstring nennt seine Flächen ehrlich). |

## F. Gesamturteil: **FAIL**

**Blockierend (Nacharbeit nötig, DEC-0088 (b) — eine Nacharbeit plus eine kurze zweite Runde nur über diese Punkte):**
1. **AC-10 / B2** — die (g)-Zusammenfassung an ihre eigenen Zahlen anpassen. Reine Textarbeit, kein Stempel, kein Lauf.
2. **AC-6 / B1** — entweder Arm B fahren oder den Grund messen und als Provider-Beobachtung ablegen.

**Nicht rundenblockierend, gehört als benannte Reste in die Löcherliste bzw. in die Nacharbeit, wenn sie ohnehin
läuft** (alle drei mit gemessenem Einzeiler-Fix, keine mit einer Angriffskette):
3. **B3 / AC-2** — `derived|Ableitung` aus der Negation. Mechanismus: *ein Wort im selben Satz hebt die gesamte
   Prüfung auf, und es ist das häufigste Wort dieser Textfamilie* — nicht „diese zwei Schreibweisen".
4. **B4 / AC-4** — Negation auf die verneinte **Anordnung** einschränken; dazu `Pruefer` (ASCII-Umschrift) in
   `_VERIFIER_RX`, weil der Codex-Zwilling in Umschrift geschrieben ist.
5. **B5 / AC-5** — ein Leser für die Erstkontakt-Frage in beiden Zwillingen.
6. **P1** — den 41-Zeilen-Rot-zuerst-Lauf (`red_first-20260911-045313.log.json`) ins Staging legen und in EVD/§3a
   nennen; sonst überlebt die Zahl den Beleg nicht.
7. **P2, P3, P4, P5, P6, P7** — Prosa/AC-Wortlaut, je ein bis zwei Zeilen.

**Außerhalb PR-0011, nur als Beobachtung gemeldet:** die `Agent|Task`-Registrierung der drei Kits nennt kein
`timeout` (`settings/settings.json`), und die Runde hat genau diesem Eintrag Arbeit hinzugefügt (Spiegel +
Partition). Heute ohne Folge (Standardfenster ~600 s gegen gemessene 1,9–3,4 s), aber es ist die Zeile, an der ein
getöteter Hook ein ALLOW wäre.

**Eigene Korrektur:** mein Zwischencheck-Befund „`test_no_shipped_kit_text_still_names_the_retired_user_gated_ladder`
fällt" war ein Artefakt meiner Kopie ohne `.git`; diesmal habe ich die Kopie zu einem echten Git-Baum gemacht, bevor
ich `test_radar_trigger` gefahren habe — 18 passed. Und meine Zeile B6 des Zwischenchecks („der Spiegel kostet
Sekunden pro Spawn") habe ich in dieser Runde **nicht** unter Last nachgemessen; sie steht als unvermessen oben.
