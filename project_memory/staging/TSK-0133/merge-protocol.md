# TSK-0133 — Merge-Runde Generation 5 (PR-0008 / PR-0009 / PR-0010), Merge-Protokoll

Basis: `feat/harness-v2` @ `b7f282e`, Haupt-Checkout `C:/Offline Repos/AgentAndSkills`; Arbeitsbaum
beim Start NICHT sauber (`project_memory/**` Kernel-Schreibungen, `docs/POST_V2_WISHLIST.md` vom
Reindex 17:36). Drei Ströme, drei Patches, jeder mit eigenem PASS. Umsetzer: Fable 5.1, effort high
(`DEC-0081` (2)). Arbeitsverzeichnis: `C:/Offline Repos/v2-testbed/_round-scratch/TSK-0133/`.
Kein Commit, kein Push, keine Installation. **Jede Uhrzeit ist gelesen (`date`), keine hochgerechnet.**

---

## Vorgefunden (Wiederaufnahme 2026-09-10, Uhr gelesen 23:01:51)

Die Sitzung dieses Umsetzers endete am 2026-09-07 mit dem Wochenlimit der API; der Lead las den
letzten Stand als „81 %, Lauf läuft". **Gemessen auf der Platte vor jedem Handgriff:** der
Lieferlauf (Versuch 2, 22:35:17) ist NICHT gestorben — `run-full-suite.txt` trägt die Endzeile
`3 failed, 4841 passed, 14 skipped, 1 warning in 6827.53s (1:53:47)`, `rc=1`, `DONE 2026-09-07
00:29:09`; die drei Roten stehen in §10 mit ihrer Auflösung. HEAD `b7f282e`, 81 geänderte Dateien
außerhalb `project_memory/` (15 neue, alle gestaged), Stempel dev/office/research **2026.09.06-1**
(unverändert seit 21:14:40), DEC-0089 angewendet (`radar/routine.json` 20:47, die fünf Texte nennen
die Entscheidung), Index mit H188, `ruff` und `validate.py` grün, kein pytest-Prozess. Dieses
Protokoll hatte 17 Abschnitte und vier PENDING-Stellen (§10, §11, §16); die Gate-Suite war noch
nicht gelaufen. Weiter ab dem letzten gemessenen Schritt: die drei Roten des Lieferlaufs.

**Was NICHT mehr auf der Platte liegt (Prüfrunde 1, P3):** das Log des Versuchs 2 wurde vom
Versuch 3 überschrieben (beide schrieben `run-full-suite.txt`, die Zeile ist Gate 5s Evidenzpfad);
die Zahlen des Versuchs 2 (`3 failed, 4841 passed, 14 skipped in 6827.53s`, DONE 00:29:09) stehen
in diesem Protokoll aus der Lesung dieses Umsetzers am 2026-09-07 00:29 und am 2026-09-10 23:01
(Vorgefunden), nicht aus einer erhaltenen Datei; nur der abgebrochene Versuch 1 ist gesichert
(`run-full-suite-attempt1-aborted.txt`). Jeder spätere Lauf dieser Runde schreibt sein eigenes Log
(`reading-suites-after-fixes.log`, `redfirst-full.log`, die Runde-1-Nachläufe unten).

## 0. Der verworfene Weg (eine Zeile, FR-0084-Form)

Verworfen: die drei Ströme als `git merge` über ihre Arbeitsbäume (`_worktrees/g5-*`) zusammenzuführen
— abgelehnt, weil ein Arbeitsbaum neben dem Patch vorläufige `VERSION`-Stempel, Rig-Reste und (in
`g5-stock`) Kernel-Schreibungen trägt, die schon im Hauptstore liegen, und weil das Paket, das die
Prüfer bestanden haben, der PATCH ist (Generation-3-Regel). **Der kleinere Weg** — die drei Patches in
Dateilisten-Reihenfolge anwenden, ohne Handauflösung — hätte die fünf Dateien nicht abgedeckt, die
alle drei Ströme berühren (`README.md`, `phase0-disposition.md`, `kernel/cli.py`, Büro-Verfassung,
`lead_package_sizes.json`): dort hat `--3way` Marker hinterlassen oder, beim Größenrekord, eine
Zahl, die keiner der drei gemessen hat.

---

## 1. Eingangsmessung der drei Patches (`patch_intake.py`, `patch_intake.log.json`)

| Strom | Patch | Bytes | Köpfe | Zeilen | CR-Bytes | VERSION-Hunks | project_memory-Hunks | `apply --check` gegen den Hauptbaum |
|---|---|---|---|---|---|---|---|---|
| G5-2 ladders (TSK-0130) | `_round-scratch/TSK-0130/stream-ladders.patch` | 296 181 | 31 | 4287 | **0** | **0** | **0** | rc 0 |
| G5-3 office (TSK-0132) | `_round-scratch/TSK-0132/stream-office.patch` | 270 991 | 28 | 4356 | **0** | **0** | **0** | rc 0 |
| G5-1 stock (TSK-0131) | `_round-scratch/TSK-0131/stream-stock.patch` | 258 531 | 37 | 3720 | **0** | **0** | **0** | rc 0 |

**Kein Patch trägt einen VERSION- oder project_memory-Hunk** — kein Zuschnitt-Befund an dieser Stelle.

**Die Nahtreihenfolge ist aus den Dateilisten gemessen, nicht angenommen** (paarweise Überschneidung):

| Paar | gemeinsame Dateien |
|---|---|
| ladders × office | 6: `README.md`, `docs/reviews/phase0-disposition.md`, `team-kits/kernel/cli.py`, Büro-`AGENTS.md`, `tools/constitution_section_pins.json`, `tools/lead_package_sizes.json` |
| ladders × stock | 9: die 6 obigen minus Pins, plus dev-/research-`AGENTS.md`, `tools/test_hooks.py`, `tools/test_hooks_v2.py` |
| office × stock | 7: `README.md`, Disposition, `cli.py`, Büro-`AGENTS.md`, `office-manager/SKILL.md`, Größenrekord, `tools/test_kernel.py` |
| in allen drei | 5: `README.md`, Disposition, `cli.py`, Büro-`AGENTS.md`, Größenrekord |

Reihenfolge **G5-2 → G5-3 → G5-1**, wie im Auftrag erwartet, und die Listen widersprechen dem nicht:
G5-1 ist der Strom, dessen Sätze auf G5-2s Absatz ZEIGEN (der PM-SKILL-Schritt „constitution's ladder
paragraph", der Wächter `_states_the_scaling_rule` über G5-2s §11/§7) und dessen `test_hooks.py`-Hunks
in denselben Funktionen liegen, deren Signaturen G5-2 ändert — wer empfängt, kommt zuletzt. G5-3
berührt mit G5-2 nur Rekord-Dateien und die Büro-Verfassung in getrennten Sektionen.

---

## 2. Anwendungslauf (Uhr gelesen)

| Schritt | Uhr | Ergebnis |
|---|---|---|
| G5-2 ladders, `git -c core.autocrlf=false apply --3way` | 20:19:36 | rc 0, 31/31 sauber (Index gestaged) |
| Pin-Leser nach Patch 1: `test_shortening_net, test_context_budget, test_disposition, test_model_pins` | 20:20:12–20:23:59 | **91 passed** |
| G5-3 office, `--3way` | 20:24:28 | **rc 1, NICHTS angewendet**: `docs/POST_V2_WISHLIST.md: does not match index` (der Reindex des Arbeitsbaums) — `git apply` ist atomar, auch die 27 sauberen Köpfe blieben draußen (gemessen: kein `docs/office/`, keine Marker) |
| G5-3 office, `--3way --exclude=docs/POST_V2_WISHLIST.md` | 20:25:41 | rc 1 mit Konflikten in 2 Dateien (Disposition, Größenrekord), 25 sauber; die WISHLIST-Hunk allein (`office-wishlist.patch`, aus dem Patch geschnitten) danach gegen den Arbeitsbaum: **rc 0** |
| Konflikte von Hand (`resolve_conflicts.py both` / `ours`) | 20:26 | Disposition: 2 Blöcke, beide Seiten behalten (Journale sind additiv); Größenrekord: vorläufig `ours`, am Ende neu gemessen (§9) |
| Pin-Leser nach Patch 2 | 20:27:09–20:29:35 | 88 passed, **3 failed** — alle drei die erwartete Naht: `office-team: lead instruction package is 61223 bytes (> 58599 recorded)` = 56 745 + 1 854 (G5-2) + 2 624 (G5-3), additiv; plus `VERSION not bumped` |
| G5-1 stock, `--3way` | 20:30:10 | rc 1, Konflikte in 5 Dateien: drei Verfassungen (§0-Kommandozeile: `ladder` gegen `sweep-pointers`), Disposition, Größenrekord; `README.md` und `tools/test_hooks.py` (die drei Hunks in G5-2s geänderten Funktionen) vom 3-Wege-Merge selbst vereinigt |
| §0-Zeile ×3 als Vereinigung (`resolve_surface_line.py`: theirs + `ladder` hinter `dispatch`), Disposition `both`, Rekord `ours` | 20:31 | `check_surface_lines.py`: alle vier Kommandolisten tragen `dispatch, ladder, submit-result` UND `migrate-holes, sweep-pointers, report-gap`, 0 Marker |
| Pin-Leser nach Patch 3 | 20:32:44–20:34:57 | 86 passed, 5 failed — wieder nur die Rekord-Naht (4× Größe, 1× Sektions-Pin), beide am Ende EINMAL aufgezeichnet (§9) |
| `git add -N` | — | nicht nötig: `--3way` staged neue Dateien als `A` (15 neue Dateien, darunter G5-3s sieben); `radar/routine.json` (neu, diese Runde) mit `git add -N` |

Eine Linie, die diese Runde NICHT gefahren hat: `normalise_line_endings` — alle drei Patches 0 CR-Bytes,
`.gitattributes` pinnt `eol=lf` seit Generation 4.

---

## 3. Nahttabelle — Auflösung und Schiedsrichter (die elf Nähte des Auftrags)

| # | Naht | Auflösung | Schiedsrichter, gemessen |
|---|---|---|---|
| 1 | `team-kits/kernel/cli.py` — drei Kommandoblöcke | alle drei Patches sauber (G5-2 `ladder` + `dispatch`-Stderr-Zeile; G5-3 `remedy_flags`; G5-1 `sweep-pointers` + `capture DEC work`-Tür + Stock-Rollup) | `ast_union.py`: Basis 26 Definitionen / 24 `add_parser`-Konstanten, Vereinigung 27 / 26, **gemergt 27 / 26**, 0 fehlend, 0 überzählig; neu gegen Basis: `ladder`, `sweep-pointers`, `remedy_flags` |
| 2 | die drei Verfassungen | G5-2s Leiter-Absätze (§11 dev/research, §7 office) + `ladder` in §0; G5-1s Kommentar-Pflicht §5a ×3 byte-identisch, CR-Frage (dev UND research — G5-1s Runde-2-Entscheidung R6: research hat `SUPERSEDED`, office nicht) und `sweep-pointers` in §0; G5-3s Andockstellen- und Korrespondenz-Pflicht (office §5/§6). Einziger Handgriff: die §0-Zeile als Vereinigung ×3. **Pins zweimal neu geschrieben**: einmal nach dem Zusammenführen (16 Sektionen, 20:56:05, §9) und einmal für den Fix M11 am Büro-Manager-Skill (eine Sektion, 2026-09-10 23:05:54, §10) — die Verfassungen selbst blieben ab 20:31 unverändert | `tools/test_role_contracts.py::test_a_paragraph_the_constitutions_share_is_one_text` + `tools/test_review_procedure.py::test_every_constitution_carries_the_comment_discipline_duty`: grün auf dem Baum, **rot** unter Ein-Wort-Drift (Rig m09); `tools/test_shortening_net.py` grün nach dem Pin (§9); `tools/test_hooks.py::test_every_span_that_presents_the_command_surface_names_all_of_it` **rot**, sobald eine §0-Liste ein Kommando verliert (Rig m08) oder der Kernel eines umbenennt (m19) |
| 3 | `team-kits/*/agents/*.md` | G5-1s Pflichtsatz in 9 bauenden Rollen kam mit dem Patch; G5-2 hat dort NICHTS geschrieben (sein Protokoll 2 (a)) — die Büro-`effort:`-Frage bleibt `BUG-0251`/H169 | `tools/test_review_procedure.py::test_every_implementing_role_definition_carries_the_comment_duty` (in den 39 grünen von 20:46); `tools/test_model_pins.py` 5 grün ×3 Läufe; `tools/test_ladder.py::test_every_kit_role_has_a_class_and_every_classed_role_ships` in der Vollsuite (§10) |
| 4 | PM-SKILLs ↔ G5-2s Absatz, `STALE_LADDER_TEXTS` | G5-1s Schritt („the rung and the effort come from THIS kit's ladder, as the constitution's ladder paragraph states it") kam mit dem Patch und zeigt auf einen Absatz, der jetzt IST (G5-2s §11: eine fettgeführte Aussage mit Sprosse `sonnet < opus < fable` als Wert und dem Feldnamen `effort` im eigenen Block; dev 1/35, research 1/35, office 0/27 — der Büro-SKILL spricht nicht über Skalierung). `STALE_LADDER_TEXTS` = `{}` — alle fünf Einträge tot | `tools/test_model_ladder.py::test_no_shipped_kit_text_still_names_the_retired_user_gated_ladder` grün mit leerer Karte; **rot** an beiden Enden: eine Vorlage spricht den Schritt wieder (m06), ein toter Eintrag bleibt (m07); `tools/test_review_procedure.py::test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule` grün, **rot** ohne den Zeiger (m18) und ohne die Effort-Achse im Absatz (m05, EINE Änderung — die N4-2-Messung des Prüfers auf dem gemergten Baum) |
| 5 | drei `templates/project_memory/project_config.yaml` | von Hand umgeschrieben: „Model ladder: haiku < sonnet < opus" → drei Sprossen `sonnet < opus < fable` (DEC-0076), `light`/haiku als vom Generator verweigert benannt, „ESCALATION … sonnet-high -> … opus-xhigh/max" → die Sprosse wird vom Kernel abgeleitet (Zeiger auf den Verfassungsabsatz, DEC-0077/0078), der Effort-Satz sagt, was abgeleitet und was gestempelt wird (BUG-0251) | dieselbe Tripwire wie Naht 4 (m06 rot); `python tools/validate.py` grün; die Behauptung „der Generator verweigert `light`" hält `tools/test_model_ladder.py::test_the_generator_refuses_a_retired_rung_pin_with_a_sentence_naming_the_decision` (G5-2) — in der Vorlage steht dazu der DEC-Zeiger, kein Testname (Nutzerprojekt-Datei) |
| 6 | `kernel/migrate.py` `_receipt_fields` | `DEC_WORK_FIELD: DEC_WORK_NONE` in das `fields`-Dict (Import aus `backlog_types`), Kommentar mit dem Warum (DEC-0083 (2)(c), DEC-0021) und dem Testnamen. **Beide Forderungen des Auftrags erfüllt statt gegeneinander ausgespielt:** der Runde-4-Test `test_the_receipt_filter_drops_the_receipt_and_nothing_else` und der Filter bleiben (der Merge-Prüfer misst sie), ein NEUER Test hält die Zeile selbst und liest `validate_state` ohne den Filter; der Filter-Docstring sagt, dass er auf der heutigen Quittung nichts mehr fällt und warum er trotzdem steht | `tools/test_migrate.py::test_the_run_receipt_carries_work_none_and_owes_no_carrier_warning` **rot ohne die Zeile** (m01); N4-1 auf dem gemergten Baum: „Filter verwirft jeden Befund über die Quittung" **rot** (m03); N3-B1 „Filter fällt auf den Typ zurück" **rot** (m04); die ganze `tools/test_migrate.py` läuft in der Vollsuite (§10) |
| 7 | `office-manager/SKILL.md` | G5-1s `work`-Klausel (Zeile 187) und G5-3s Abschnitt „Letters that leave the house" (Zeile 221) beide da, getrennte Hunks, kein Handgriff | `grep` beider Marker; `tools/test_review_procedure.py::test_every_lead_skill_says_who_carries_a_decision` **rot** ohne die Klausel (m17); der Brief-Schritt: `tools/test_office_package.py` im Lieferlauf |
| 8 | Rekorde + README-Kommandofläche | `tools/lead_package_sizes.json` EINMAL neu aufgezeichnet über den gemergten Baum (`record_lead_package_sizes.py --write --note`, 20:55:59): dev 53 581 → **56 138** (+2 557), office 58 599 → **62 397** (+3 798), research 55 918 → **58 060** (+2 142); die Journalzeilen aller drei Ströme bleiben additiv davor. `tools/constitution_section_pins.json` EINMAL neu gepinnt (16 Sektionen, 20:56:05). README nennt `ladder` UND `sweep-pointers` | `python tools/validate.py`: all structural checks passed (21:14:44); `test_context_budget` + `test_shortening_net` in der Vollsuite; Kommandoflächen-Tripwire (m08/m19 rot) |
| 9 | Session-Brief (PR-0010 AC-6, BUG-0249/H167) | `report.generate_session_brief`: die `TSK`-Zeile trägt `rung`/`effort`, wenn das Item sie trägt (Feldnamen aus `dispatch.RUNG_KEY/EFFORT_KEY`, kein zweiter Schlüssel); ein nie dispatchter Auftrag zeigt nichts. **Auftragsdefekt geschlossen:** PR-0010s Item hatte G5-2 `report.py` verboten, das AC-6 verlangte | `tools/test_report.py::test_the_session_brief_shows_the_rung_and_effort_a_lease_wrote_on_the_task` **rot ohne die Zeile** (m02); Brief-Schema (`item_required` ohne `additionalProperties`) unverändert grün |
| 10 | `.claude/hooks/test_gates.py` | **kein Strom hat die Datei angefasst** (in keiner der drei Dateilisten) — keine AST-Vereinigung nötig | Dateilisten (`patch_intake.log.json`); die volle Gate-Suite mit Präfix in §10 |
| 11 | Zeiger gegen den LIVE-Store | siehe Zeigertabelle §7: die DEC-0082/0083-Zitate, die gegen den b7f282e-Store rot waren, sind hier grün | `tools/test_repo_hygiene.py` + `tools/test_review_procedure.py -k "pointer or hole or resolves"`: **13 passed** (21:07:49–21:10:39); `.claude/hooks/test_gates.py -k hole`: **6 passed** (21:10:39–21:12:11) |

---

## 4. Merge-Befund DEC-0089 — der Radar-Mechanismus, den kein Strom sehen konnte

Die Lead-Nachricht kam um 20:2x, DEC-0089 (erfasst 20:21:14, löst DEC-0085 ab). **Nachgemessen, nicht
übernommen** (`ls --time-style=full-iso radar/`, 20:25): `2026-07-17 20:10:27`, `07-24 20:12:23`,
`07-31 20:16:57`, `08-07 20:47:19`, `08-21 20:16:33`, `08-28 20:12:08` — Freitage —, `08-16 20:25:42`
ein Sonntag; alle mit `-claude`-Suffix; die Desktop-Task-Datei `~/.claude/scheduled-tasks/radar-watcher/SKILL.md`
(1093 B, 2026-06-30 10:53:59) delegiert an `.claude/agents/radar-watcher.md`. Die Behauptung von
BUG-0269 („der Bericht trägt kein Suffix") war falsch; DEC-0089 stimmt mit den Artefakten überein.

**Umgeschrieben (Träger DEC-0089 (5)):**

| Datei | vorher (G5-2, DEC-0085) | nachher |
|---|---|---|
| `tools/radar_routine.py` | Cloud-Routine „der Mechanismus"; `starts_itself` aus `radar/routine.json`-`triggers` (RemoteTrigger-Ids); Desktop-Task unter `other_shapes`, „state unknown, never counted" | Mechanismus = Desktop-Task je Watcher; `starts_itself` **je Watcher** abgeleitet aus zwei Dingen: dem Eintrag des Leads in `radar/routine.json` (`desktop_tasks`: kind, watcher, path, Zeitplan WIE VOM NUTZER GESAGT mit Quelle, erster/letzter gemessener Bericht) UND der Kadenz-Evidenz in den Berichten (≥ `CADENCE_EVIDENCE_MIN` = 2 Berichte des Watchers am aufgezeichneten Wochentag, gelesen aus den DATEINAMEN, damit ein Klon dasselbe antwortet); ob die Task-Datei auf DIESEM Host liegt, wird gemeldet und von keinem Text-Urteil gelesen (ein CI-Klon darf einen wahren Satz nicht falsch machen — die Abweichung von DEC-0089 (3) „exists" und ihr Grund stehen im Modul-Docstring); die Cloud-Spezifikation bleibt als `cloud_option` mit `built: false`, `rejected_by: DEC-0089` |
| `tools/test_radar_trigger.py` | Regel in zwei Zuständen (Cloud aufgezeichnet / nicht) | Regel **je Watcher** (`schedule_claim_offence`): ein Anspruchssatz nennt den Mechanismus (Modul oder Desktop-Task) oder ist verweigert (die Cloud-Routine nennt beides nicht → verweigert in JEDEM Zustand); die Watcher, um die es geht, sind die genannten oder beide; wo einer ohne aufgezeichnete Task mit Kadenz ist, muss der Satz sagen, wer startet. Anspruchswörter erweitert um `desktop (task|routine|app)`, `claude.ai`, `cloud routine`, `remotetrigger`, Wochentage. „fires only while the app is open" ist ein Anspruch über den Mechanismus, kein Disclaimer (DEC-0089 (4)) — die zwei alten Ausnahme-Schreibweisen stehen jetzt als Ansprüche im Leser-Test |
| `radar/README.md` „How a run starts" | zwei Hälften, Cloud + Sitzung | DEC-0089: Radar-Task existiert und läuft (Freitage, gemessen), Codex-Task legt der Nutzer an (Samstag ~20:00), bis dahin startet der Lead von Hand; verworfene Alternative benannt; die Grenze (Zeitplan nicht auf der Platte, App muss offen sein, Nachholen binnen sieben Tagen) benannt |
| `.claude/agents/radar-watcher.md`, `codex-watcher.md` | „a claude.ai code routine the lead owns" | Radar: Desktop-Task freitags (DEC-0089, `radar/routine.json`); Codex: keine aufgezeichnete Task, Lead startet mit `--run` |
| `radar/routine.json` (NEU) | — | der Radar-Eintrag mit Zeitplan (friday, ~20:00, „as told by the user 2026-09-06 (DEC-0089)"), Quelle (die mtimes), erster/letzter gemessener Bericht 2026-07-17 / 2026-08-28; der Codex-Eintrag ist des Leads, sobald die Task existiert |
| `BUG-0269`/H186 | Suffix-Behauptung, „never counted as live" | durch den Kernel korrigiert (`update BUG-0269`, 21:03:07, rc 0): Titel, observed, expected, repro, AC, limits, source — Mechanismus = die Task, Suffix-Satz weg, Grenze als dokumentierte Grenze; Testnamen auf die neuen Leser |

**Gemessen auf dem gemergten Baum** (`describe-merged.json`, 20:51:23): `mechanism` = „a Claude
Desktop scheduled task per watcher …", `starts_itself` = `{radar-watcher: true, codex-watcher: false}`,
`cadence_evidence` radar = 2026-07-17, 07-24, 07-31, 08-07, 08-21, 08-28, 09-04 (sieben Freitage),
`task_file_present_on_this_host: true`, `cloud_option.built: false`; `--due`: „no watcher owes a run
in 2026-W36". `tools/test_radar_trigger.py` 9 passed (20:55:46) — nachdem der Leser DREI meiner
eigenen README-Sätze verweigert hatte (20:51, 20:53, 20:54: ein Grenz-Satz ohne Watcher-Nennung, ein
Satz mit „cloud routine", der Einleitungssatz ohne Starter für die Codex-Hälfte) — jeder umformuliert,
nicht der Leser gelockert. **Rot ohne den Fix:** README nennt die Cloud-Routine wieder als Mechanismus
(m10), Codex-Text behauptet eine Samstags-Task (m11), `starts_itself` ohne Kadenz-Evidenz (m12), jede
Art zählt als Task (m13), fremde Suffixe zählen (m14), `--describe` nennt die Cloud den Mechanismus
(m15), Konstante `True` (m16).

**Nicht angefasst (Weisung des Leads):** `staging/TSK-0130/dec-trigger-2.json`. **Nicht angefasst
(verboten):** die vier Zeitplan-Sätze in `.claude/hooks/` (BUG-0264/H182).

---

## 5. Merge-Befunde — was die Nähte zeigten, das kein Strom sehen konnte

| # | Befund | Erledigt als |
|---|---|---|
| M1 | DEC-0089 (Abschnitt 4) | umgeschrieben, rot-zuerst, Item korrigiert |
| M2 | `git apply --3way` verweigert einen Patch ATOMAR, wenn eine seiner Dateien im Arbeitsbaum verändert ist (`does not match index`) — 27 saubere Köpfe blieben mit draußen und die Meldungen „Applied … cleanly" davor waren Vorprüfungen | Patch ohne die Datei, Hunk allein gegen den Arbeitsbaum; Prozessnotiz für die nächste Merge-Runde |
| M3 | Größenrekord: `--3way` liefert für eine Zahl, die drei Ströme je einmal gemessen haben, einen Konflikt, dessen beide Seiten falsch sind | vorläufig `ours`, am Ende EINE Messung mit `--write --note` |
| M4 | Naht 6 verlangte „die Zeile mit ihrem Test" UND das Überleben des Runde-4-Filtertests, dessen Docstring „bis der Merge sie schließt" sagte — nach der Zeile fällt der Filter auf der heutigen Quittung nichts mehr | beides gebaut; Filter-Docstring wahr gemacht; neuer Test liest OHNE den Filter (sonst würde der Filter die Regression der eigenen Zeile an zehn Stellen verstecken); der Rest (Filter + zehn Stellen zurückbauen) in §15 benannt |
| M5 | BUG-0270/H187 („Der Zeiger-Sweep dieses Repos liest … nicht `tools/`") liest sich wie das Kernel-Kommando `sweep-pointers`, das auf dem gemergten Baum `tools/` sehr wohl liest (6 der 30 Funde) — gemeint ist der Leser `tools/test_repo_hygiene.py::_texts_that_answer_for_a_claim`, den `observed`/`repro` benennen | kein Widerspruch in der Sache, ein zweideutiger Titel; in §15 benannt, Item nicht geändert |
| M6 | Gate 1 verweigert einen reinen `grep` mit maskierten Backticks UND Leerzeichen im quotierten Wort als Schreibzugriff auf `C:\` (Ketten §8/§15) — dabei ist ein `git add` hinter dem grep in derselben Zeile still ausgefallen und wurde erst an der nächsten Prüfung bemerkt | Loch **BUG-0272/H188** durch den Kernel (21:18:05) |
| M7 | Gate 3 las `git -C "<Pfad mit Leerzeichen>" add -A -- …` als unbekanntes Unterkommando „repos/v2-testbed/…"; drei engere Proben (`status`, `add --dry-run`, mit Pipe) gingen rc 0 durch — **nicht isoliert** | kein Loch (ein Loch ohne Mechanismus ist eine Behauptung); die verweigerte Zeile und die drei Proben stehen in §15 |
| M8 | Nach dem Update von BUG-0269 trug der Zeigerindex den alten Titel (`test_every_hole_is_one_index_row_one_prose_file_and_one_item` wäre rot) | `migrate-holes --reindex` selbst gefahren (21:07:32 → 177; 21:18:33 → 178) — die Zeile war dem Lead zugedacht, Gate 1 ließ sie diesem Umsetzer durch; läuft der Lead nach dieser Runde weitere Löcher, fährt er sie erneut |
| M10 | G5-3s `letter_draft.py` gegen die DEC-0024-Regel aus `test_migrate` (§10, Lieferlauf Versuch 2) | zwei Literale, Rig m21 rot |
| M11 | G5-3s Referenz-Skill `correspondence` ohne Route in einem Text des Sitzungsagenten (`test_parallel_streams`, §10) | eine Routen-Zeile im Büro-Manager-Skill, Rig m22 rot |
| M12 | CRLF-Arbeitskopie zweier Gen-4-Staging-Dateien im Hauptcheckout (§10) | außerhalb des Bereichs; Zeile des Leads benannt |
| M13 | **Gate-Suite, voll (§10):** `test_gate2_refuses_an_archived_item_whose_type_declares_no_terminals` nimmt eine `DEC` über die CLI mit einem festen Rumpf ohne `work` auf — G5-1s DEC-0083-Tür erreicht `.claude/hooks/test_gates.py` (in voller Länge von keinem Strom gefahren; G5-1 fuhr `-k "hole or …"`), dieselbe Klasse wie M9 | der Rumpf trägt `work: DEC_WORK_NONE`, und die Typwahl fragt `CAPTURE_ONLY_REQUIRED` mit — die Felder werden aus dem Kernel gelesen, nicht getippt; Rig m23 **rot** |
| M14 | **Gate-Suite, voll:** `_hole_prose` (Helfer von vier Tests) öffnete das `source`-Feld JEDES Lochs als Datei — wahr nur für die 155 migrierten (`source` = `docs/holes/H<n>.md`, gemessen), falsch für die 23 seit Generation 4 per `capture --hole` erfassten (Prosa oder leer): `test_every_reference_to_a_measurement_leads_to_one` fiel mit `FileNotFoundError` an H166 (G5-3), und wäre an H167/H168/H178/H182/H184/H186/H188 ebenso gefallen. Ein Leser, der weniger las, als sein Docstring behauptete — die Klasse aus DEC-0080 (6), diesmal in der Gate-Suite selbst | `_hole_prose` nimmt das Prädikat des Kernels (`holes._prose_link`: die Datei `docs/holes/<n>.md` existiert) und liest sonst die Textfelder des Items — die 23 erfassten Löcher werden damit ERSTMALS gegen ihre Protokoll-Verweise gelesen; Rig m24 (Pfad aus `source`) **rot** |
| M15 | Der erweiterte Leser (M14) las die 23 erfassten Löcher zum ersten Mal und fand EINEN Verstoß: H181 (BUG-0263, G5-3) zitiert `docs/reviews/2026-09-02-tsk0107-office-duties-measurements.md`, das den Eintrag `H181` nicht trug — das Item nennt das Dokument als eines mit zwei Zitaten unter seinem ersten Codezaun, die niemand beurteilt und die tot sind (zwei umbenannte Tests); die anderen 22 Löcher zitieren kein Messprotokoll (H178 zitiert die Disposition, die H178 trägt) | datierter Nachtrag im Dokument, der die Beziehung zu H181 und die zwei toten Zitate benennt (die Messungen darüber unverändert); Test grün, siehe §10 |
| **Prüfrunde 1 (2026-09-11 00:33–01:09, Opus): vier Blocker, sechs Reste — jeder eine Zeile im gemergten Baum, kein Kit-File, kein Neustempel** | | |
| R1-B1 | die zwei Laufprotokolle dieser Runde (`run-full-suite.txt` 119, `run-gates-suite.txt` 9 CRLF-Paare) waren unverfolgt UND CRLF: gestaged hätten sie `test_no_tracked_text_file_checks_out_with_crlf` rot gemacht, und der Normalisierer verweigert Unverfolgtes — Ursache: die Shell-Umleitung von pytests Textstrom unter Windows | `lf_logs.py`: beide binär auf LF (119 → 0, 9 → 0, kein anderes Byte), §13 sagt es; jedes weitere Log dieser Runde ebenso geschrieben |
| R1-B2 | Rig m23 war GRÜN, nicht rot: `candidates[0]` fiel ohne `work` still auf `INV` (mit: `['DEC','INV']`, ohne: `['INV']`) — mein Kommentar behauptete Deckung, die der Test nicht hatte | der Gate-2-Test läuft über ALLE Kandidaten und verlangt `DEC` darunter; m23 = die Mutation des Prüfers (Dict verliert `work`) **rot**, m25 (Rumpf verliert die Tür-Felder) **rot**; Kommentar sagt, was gemessen war |
| R1-B3 | `schedule_claim_offence` war ein positiver Wort-Test: „The claude.ai cloud routine starts the radar-watcher every Friday from the Desktop." passierte, weil `Desktop` genannt war | die Erklärung veröffentlicht die Namen der nicht gebauten Option (`cloud_option.named_as`), und ein Satz, der eine solche nennt, wird ZUERST verweigert, was immer er sonst sagt; v01 = Rig m26 **rot**; Docstring und Modulkopf sagen es |
| R1-B4 | `_states_the_scaling_rule` las den ganzen 1424-Zeichen-Punkt: die Effort-REGEL entfernt, drei beiläufige `effort`-Nennungen blieben, Test grün (w01) | die Achse gilt dort, wo sie Regel ist — im Fett-Lead-in oder in EINEM Satz mit einer Sprosse als Wert; gemessen: dev 1/36, research 1/36, office 1/32 (die Ablage-Paar-Aussage; dort wird die Zahl nicht behauptet), w01 → 0 = Rig m27 **rot**; die Verfassungen sind RICHTIG und unberührt |
| R1-P1 | `_hole_prose`-Docstring behauptete, `holes._prose_link` zu benutzen | sagt jetzt, was die Zeile tut (dieselbe Frage, direkt am Pfad) |
| R1-P2 | BUG-0272 `observed`: zwei der drei Kontroll-rcs falsch (`grep -c` ohne Treffer ist rc 1, das Gate hatte sie durchgelassen) | `update BUG-0272` durch den Kernel (01:17:22) |
| R1-P3 | Log des Versuchs 2 überschrieben | im Vorgefunden-Absatz gesagt; eigene Namen für jedes weitere Log |
| R1-P4 | §16-Zahlen | Zählbefehl und Ergebnis stehen in §16 |
| R1-P5 | Naht 2 „Pins einmal" gegen §10 „neu gepinnt 23:05" | Naht 2 sagt zweimal, mit beiden Uhrzeiten |
| R1-P6 | ein Kadenz-Satz ohne Anspruchswort („The watcher duo runs once a week without a human.") passiert den Leser gebaut-gemäß | Loch **BUG-0273/H189** durch den Kernel (01:17:2x), Index 179; der Satz steht als benannte Grenze im Leser-Test mit dem Item |
| M9 | **G5-1s DEC-0083-Tür erreichte eine Suite, die kein Strom gelesen hat** (DEC-0080 Regel 2, dieselbe Klasse wie die 435 Roten der Generation 4): `tools/test_e2e.py` nimmt in zwei Tests eine `DEC` über die Kommandofläche auf, ohne `work` — im ersten Lieferlauf-Versuch die einzigen zwei `F` (Testindizes 449/451, beide `test_e2e`; allein gefahren 22:32:12: `2 failed, 18 passed`, Fehltext „capture DEC: work says nothing"). G5-1s 18 Lesesuiten enthielten `test_e2e` nicht; G5-2s Lauf 5 hatte es grün, weil sein Baum die Tür nicht trug | beide Rümpfe tragen `work: none` (Entscheidungen, die niemanden verpflichten — dieselbe Korrektur wie G5-1s in `test_kernel.py`); `test_e2e.py` **20 passed** (22:33:25–22:33:53); Rig m20 (Rückbau) **rot**; ein Grep über `tools/*.py` findet keine weitere CLI-`DEC`-Aufnahme ohne `work` und kein leeres `expected_outputs` mehr. Kein Kit-File berührt → kein Neustempel |

---

## 6. Rot-zuerst-Rig (`redfirst.py`, `redfirst.log.json`) — jede Änderung dieser Runde ohne sich

Kopie außerhalb des Repos mit ECHTEM `.git` (Klon `--no-local --no-checkout`, dann der Baum;
`fix_copy_git.py` — die erste Kopie hatte ein kopiertes `.git`, aus dem `test_migrate` keine Historie
lesen konnte: drei ERROR-Zeilen, ein Rig-Artefakt derselben Familie wie beim Runde-4-Prüfer, ersetzt
und neu gefahren), EINE Mutation je Zeile, Neustempel nach jeder Kit-Mutation, binär, verweigert
außerhalb seines Verzeichnisses. **20 Zeilen, jede wie erwartet** (20:56:31–21:06:36):

| Zeile | Mutation (Richtung: was der Satz bestreitet) | Schiedsrichter | Ergebnis |
|---|---|---|---|
| m00 | KONTROLLE, unmutierte Kopie | `test_radar_trigger` + Brief-Test | **GRÜN** (10 passed) |
| m01 | Quittung verliert `work: none` | `test_migrate::test_the_run_receipt_carries_work_none_and_owes_no_carrier_warning` | RED |
| m02 | Brief-Zeile verliert `rung`/`effort` | `test_report::test_the_session_brief_shows_the_rung_and_effort_a_lease_wrote_on_the_task` | RED |
| m03 | N4-1: Filter verwirft JEDEN Befund über die Quittung | `test_migrate::test_the_receipt_filter_drops_the_receipt_and_nothing_else` | RED |
| m04 | N3-B1: Filter fällt auf den Typ zurück | derselbe | RED |
| m05 | N4-2: G5-2s Leiter-Absatz verliert die Effort-Achse (EIN Absatz, Nachbarpunkt behält `effort:`) | `test_review_procedure::test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule` | RED |
| m06 | dev-Vorlage spricht `sonnet-high -> …` wieder (Ausbreitungs-Ende) | `test_model_ladder::test_no_shipped_kit_text_still_names_the_retired_user_gated_ladder` | RED |
| m07 | `STALE_LADDER_TEXTS` behält einen toten Eintrag (Tot-Eintrag-Ende) | derselbe | RED |
| m08 | dev-§0-Liste verliert `sweep-pointers` | `test_hooks::test_every_span_that_presents_the_command_surface_names_all_of_it` | RED |
| m09 | Kommentar-Pflicht driftet ein Wort in EINER Verfassung | `test_role_contracts::…share_is_one_text` + `test_review_procedure::…comment_discipline_duty` | RED |
| m10 | README nennt die Cloud-Routine als Mechanismus | `test_radar_trigger::test_no_text_claims_a_schedule_the_repo_does_not_build` | RED |
| m11 | Codex-Definition behauptet eine Samstags-Task | derselbe | RED |
| m12 | `starts_itself` ohne Kadenz-Evidenz | `test_radar_trigger::test_the_self_start_reader_answers_off_the_record_and_the_reports` | RED |
| m13 | jede `kind` zählt als Desktop-Task | derselbe | RED |
| m14 | Kadenz zählt fremde Suffixe | derselbe | RED |
| m15 | `--describe` nennt die Cloud den Mechanismus | `test_radar_trigger::test_the_cloud_option_says_it_is_not_built_and_its_prompt_stays_consistent` | RED |
| m16 | `starts_itself` Konstante `True` | wie m12 | RED |
| m17 | office-manager-SKILL verliert die `work`-Klausel | `test_review_procedure::test_every_lead_skill_says_who_carries_a_decision` | RED |
| m18 | dev-PM-SKILL verliert den Zeiger „constitution's ladder paragraph" | wie m05 | RED |
| m19 | `cli.py` benennt `ladder` um (Kommandofläche gegen die Listen) | wie m08 | RED |

| m20 | `test_e2e.py`: der DEC-Rumpf verliert `work: none` (§5 M9) | `test_e2e::test_e2e_capture_stores_umlaut_body_as_utf8_bytes_whatever_the_stdin_codepage` | RED |
| m21 | `letter_draft.py`: die Abhilfe nennt `staging/<TSK-ID>/correspondence.yaml` wieder (§5 M10) | `test_migrate::test_no_remedy_literal_this_repo_ships_names_a_place_inside_a_state_directory` | RED |
| m22 | Büro-Manager-Skill verliert die Codex-Route des Korrespondenz-Skills (§5 M11) | `test_parallel_streams::test_a_reference_skill_named_for_a_session_agent_is_named_by_a_text_it_reads` | RED |
| m23 | Gate-2-Test: das Felder-Dict verliert `work` (die Mutation des Prüfers, R1-B2 — die erste Fassung dieser Zeile war grün) | `.claude/hooks/test_gates.py::test_gate2_refuses_an_archived_item_whose_type_declares_no_terminals` | RED |
| m24 | `_hole_prose` liest `source` wieder als Pfad (§5 M14) | `.claude/hooks/test_gates.py::test_every_reference_to_a_measurement_leads_to_one` | RED |
| m25 | Gate-2-Test: der Rumpf trägt die Tür-Felder nicht mehr (R1-B2) | derselbe wie m23 | RED |
| m26 | v01 (R1-B3): README nennt die Cloud-Routine „from the Desktop" | `test_radar_trigger::test_no_text_claims_a_schedule_the_repo_does_not_build` | RED |
| m27 | w01 (R1-B4): die Effort-Regel verlässt die dev-Leiter-Aussage, drei beiläufige Nennungen bleiben | `test_review_procedure::test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule` | RED |

Das Rig zieht seit Prüfrunde 1 vor jedem Lauf jede geänderte Datei aus der Quelle in die Kopie nach
(`sync_copy`) — die Kopie stammt vom 2026-09-06, und eine neue Zeile hätte sonst den Leser von
damals gemessen.

Dazu die Kontrollen auf dem Hauptbaum vor dem Rig: die fünf Naht-6/9-Tests 5 passed (20:42:05–20:42:39),
`test_model_ladder` + `test_review_procedure` 39 passed (20:46:09–20:46:55).

**Der Log auf der Platte ist der zweite Lauf des ganzen Rigs**: die Teilläufe vom 2026-09-06 hatten
`redfirst.log.json` je überschrieben (nach `m20` stand eine Zeile darin — ein Rig-Fehler, behoben:
das Rig MISCHT seine Zeilen jetzt in den Log), also wurden **alle 23 Zeilen am 2026-09-10 noch einmal
gefahren** (`redfirst-full.log`, 23:11:10–23:12:33, `every row in log as expected: True`) — auf
dem Baum NACH den Fixes M9–M11 und dem Stempel 2026.09.10-1.

---

## 7. Zeigertabelle (Naht 11)

| Leser | Läuft gegen | Ergebnis |
|---|---|---|
| `tools/test_repo_hygiene.py` + `tools/test_review_procedure.py -k "pointer or hole or resolves"` (13 Tests: DEC-Zeiger in Kit-Dateien, Test-Zeiger repo-weit, Item-/Test-Zeiger der Harness-Rollentexte, Loch-Dreieck, Artefakt-Refs) | LIVE-Store (DEC-0080..0089 vorhanden) | **13 passed** (21:07:49–21:10:39) — die drei „Store-Naht"-Roten der Ströme (DEC-0082/0083, DEC-0080, TSK-0131, BUG-0251) sind hier grün |
| `.claude/hooks/test_gates.py -k hole` (6 Tests, u. a. `test_every_test_a_hole_names_is_one_that_exists`, `test_every_hole_states_a_verdict_and_an_unclosed_one_names_its_limit`) | LIVE-Store, Index nach Reindex | **6 passed** (21:10:39–21:12:11) — der fremde Rote der Ströme (H169/H171 → `tools/test_ladder.py`) löst sich, weil die Datei jetzt im Baum liegt |
| `PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory sweep-pointers` (`sweep-pointers-merged.txt`) | LIVE-Store, gemergter Kernel | **30 tote Zeiger, 0 unter `team-kits/`**: 24 in `docs/` (Platzhalter `PROC-0001`/`DEC-0001`/`RQ-0001`/`HYP-0001`/`EXP-0001` alter Messprotokolle und Pilotberichte, `tools/conftest.py::V1_MONOLITHS` ×2, zwei Beispielpfade in Research-Notizen, `hooks/_kernel.py::bundle_trust` in einem Messprotokoll) und 6 in `tools/` (vier Fixture-Zeichenketten in `test_pointer_sweep.py`, `PR-000199999` in `test_board.py`, `DEC-0001` in `test_report.py`) — alle die Illustrations-Klasse H175 (BUG-0257); G5-1 maß 26 gegen den b7f282e-Store über docs+team-kits |
| Testnamen in den neuen Kommentaren dieser Runde (`migrate.py`, `report.py`, `radar_routine.py`, `test_migrate.py`) | Baum | jeder genannte Test existiert und ist in §6 gelaufen; `.claude/hooks/test_gates.py`-Selbstprüfung der Backtick-Zitate in der Gate-Suite (§10) |

---

## 8. Lochliste nach `migrate-holes --reindex` (Index = Store, 178 Löcher, 21:18:33)

Jede Zeile ist ein Item mit `observed` (Mechanismus + Kette), `expected`/`status` (Verdikt) und
`limits` (Begrenzung); dass alle das tragen, misst
`.claude/hooks/test_gates.py::test_every_hole_states_a_verdict_and_an_unclosed_one_names_its_limit`
(grün, §7). Die Zeilen dieser Generation, in Nummernfolge (Stand des Index):

| Loch | Item | Stand | Strom | Kurz |
|---|---|---|---|---|
| H166 | BUG-0248 | OPEN | G5-3 | gemischter USt-Satz auf einer Rechnung wird „von Hand" gebucht |
| H167 | BUG-0249 | OPEN | G5-2 | Brief zeigt Sprosse/Effort nicht — **in dieser Runde gebaut** (Naht 9); Schließung durch den Lead nach dem Merge-PASS (Item nennt `report.py`) |
| H168 | BUG-0250 | OPEN | G5-2 | zwei widersprechende Leiter-Texte — die fünf `<rung>-<effort>`-Dateien sind repariert (Naht 4/5); offen bleiben `session_status.py`s `lead/worker/light`-Karte und die `light -> haiku`-Zeilen des Scaffolds |
| H169 | BUG-0251 | OPEN | G5-2 | Effort abgeleitet, nie angewandt (kein Spawn-Parameter) |
| H170 | BUG-0252 | OPEN | G5-2 | `PROC` trägt keine `class`, office-`large` unerreichbar |
| H171 | BUG-0253 | OPEN | G5-2 | Projekt ohne Scaffold-Record dispatcht mit `ladder: absent` |
| H172 | BUG-0254 | OPEN | G5-2 | Codex-Effort-Decke ungemessen (kein Codex-CLI) |
| H173 | BUG-0255 | OPEN | G5-2 | Codex: kein Spawn-seitiger Halt |
| H174 | BUG-0256 | DUPLICATE | G5-1 | Dublette zu BUG-0251 |
| H175 | BUG-0257 | OPEN | G5-1 | Sweep unterscheidet Illustration nicht von Zeiger (§7: 30 Funde) |
| H176 | BUG-0258 | OPEN | G5-3 | Loch-Tabellen-Test ohne `### H`-Korpus seit Gen 4 — **einziger erwarteter Roter der Vollsuite** |
| H177 | BUG-0259 | OPEN | G5-3 | Neutralitätsleser liest nur Listen |
| H178 | BUG-0260 | OPEN | G5-2 | narrow/mechanical hält den Aufstieg nicht mehr auf |
| H179 | BUG-0261 | OPEN | G5-1 | bestandener Test ≠ Urteil |
| H180 | BUG-0262 | OPEN | G5-1 | zweiter Zeitmess-Test rot auf beschäftigtem Host |
| H181 | BUG-0263 | OPEN | G5-3 | Backtick-Paarung über die ganze Datei blendet Zitate |
| H182 | BUG-0264 | OPEN | G5-2 | vier Zeitplan-Sätze in `.claude/hooks/` |
| H183 | BUG-0265 | OPEN | G5-1 | Sweep liest Skript-Verzeichnisse mit Kit nicht |
| H184 | BUG-0266 | OPEN | G5-2 | Auditor-Routine nicht dispatchbar auf eigener Route |
| H185 | BUG-0268 | OPEN | G5-1 | CLAUDE.md sagt vier Gates, fünf registriert |
| H186 | BUG-0269 | OPEN | G5-2 → **Merge korrigiert** | Desktop-Task: Zeitplan nicht auf der Platte, App muss offen sein (DEC-0089) |
| H187 | BUG-0270 | OPEN | G5-1 | `test_repo_hygiene`s Zeiger-Leser liest `tools/` nicht (Titel zweideutig, §5 M5) |
| H188 | BUG-0272 | OPEN | **Merge** | Gate 1 verweigert einen Lese-`grep` mit maskierten Backticks + Leerzeichen als Schreibzugriff auf `C:\` |

`BUG-0271` (20:30:43, Lead) ist kein Loch (Freigabe-Frage in Maschinendeutsch, PR-0003) und steht
nicht im Index.

---

## 9. Rekorde, Spiegel, Stempel (Reihenfolge: zuletzt geändert → aufgezeichnet → gestempelt → gemessen)

| Was | Uhr | Messung |
|---|---|---|
| Lead-Paket-Größen | 20:55:59 | dev 56 138 / office 62 397 / research 58 060 B, drei `GREW`-Journalzeilen mit Grund (Disposition §10) |
| Sektions-Pins | 20:56:05 | 16 Sektionen neu gepinnt, eine Journalzeile je Sektion, Grund: die Vereinigung; keine Regel `behalten` verloren (jeder Strom hat seine Sektionen gegen die Paritätsmatrix gemessen; der Merge hat außer der §0-Vereinigung keinen Satz verfasst) |
| Spiegel | 20:58 | `gate_dispatch.py` ×3 md5 `fd1712bf2686…`; abweichend nur `ENFORCEMENT.md`, `document_trays.txt`, `format_on_write.py`, `session_status.py`, `settings.json` — alle in `KIT_SPECIFIC_HOOKS` bzw. je Kit deklariert; `tools/validate.py` grün |
| `python -m ruff check .` | 20:58:30 | All checks passed |
| **Stempel** `python tools/bump_kit_version.py` | **21:14:40** | dev / office / research **2026.09.06-1** (die Hauptbaum-Linie zählt ab `2026.09.05-6`; die vorläufigen Stempel der Ströme — G5-2 `-2`, G5-3 office `-4`, G5-1 `-9/-8/-10` — waren Arbeitsbaum-Zähler, nie installiert, und sind ersetzt). Nach dem Stempel wurde **keine Kit-Datei mehr angefasst**; danach nur Staging, Kernel-Schreibungen (BUG-0272), Reindex (`docs/`) |
| `python tools/validate.py` | 21:14:44 | all structural checks passed |
| **Stempel nach den zwei Kit-Fixes des Lieferlaufs** (`letter_draft.py`, Büro-Manager-Skill; §10) | 2026-09-10 23:11:07 | `bump_kit_version.py`: office-team → **2026.09.10-1**, dev-team und research-team **unchanged (2026.09.06-1)** — der Stempler hebt nur das Kit an, dessen Hash sich bewegt hat, und die Zähler laufen je Kit; `validate.py` all structural checks passed (23:11:08); `ruff` All checks passed (23:06:12) |
| Gate 5, die nackte Zeile `timeout 30 python -B -m pytest tools/ -q` | 21:15 | **verweigert** von `gate_test_scope.py`: „this line runs the WHOLE declared test surface `tools` … nothing on it says this is the delivery run" mit der `DELIVERY_RUN=<ITEM-ID>`-Remedy (rc 2) — einmal als Prozess gemessen, nicht bekämpft |

---

## 10. Die volle Suite (Lieferkriterium, DEC-0080 (5): NACH dem Stempel)

| Lauf | Zeile | Start | Ergebnis |
|---|---|---|---|
| `tools/` voll, **Versuch 1 — von mir abgebrochen** | `DELIVERY_RUN=TSK-0133 timeout 5400 python -B -m pytest tools/ -q -p no:cacheprovider` | 21:17:02 | bei 45 % (2247 Marken, 2 `F` = die zwei `test_e2e`-Roten aus §5 M9) um 22:30:21 beendet (PID 33120 + `timeout`-Hüllen): der Lauf brauchte 61 min für 31 % und 73 min für 45 %, seine eigene Frist (90 min) hätte ihn um 22:47 in `test_hooks_v2` getötet — ein getöteter Lauf ist keine Evidenz. Grund der Langsamkeit **gemessen** (22:29:59): Host-Last **85 % auf 16 logischen Kernen**, fast vollständig fremd (codex, VS Code, weitere claude-Sitzungen, ChatGPT, Docker, ein `depth3_run.py`-Modelllauf einer anderen Sitzung per `nohup`) — nichts davon von dieser Runde gestartet; die „~45–60 min" des Auftrags gelten für einen leeren Host. Log gesichert: `_round-scratch/TSK-0133/run-full-suite-attempt1-aborted.txt` |
| `tools/` voll, **Versuch 2** | `DELIVERY_RUN=TSK-0133 timeout 14400 python -B -m pytest tools/ -q -p no:cacheprovider` → `project_memory/staging/TSK-0133/run-full-suite.txt` | 22:35:17 → 00:29:09 (2026-09-07) | **3 failed, 4841 passed, 14 skipped in 6827.53 s (1:53:47)**, rc 1 — drei Befunde, jeder aufgelöst (§5 M10–M12); H176 (BUG-0258) war NICHT rot: der Loch-Tabellen-Test liest seit G5-1s Neufassung Index gegen Store |
| Lesesuiten der zwei Fixes, voll (DEC-0063 (4)): `test_office_package, test_migrate, test_kit_neutrality, test_parallel_streams, test_review_procedure, test_role_contracts, test_context_budget, test_shortening_net` (`test_hooks` liest den Skill ebenfalls — im Lieferlauf darunter) | `reading-suites-after-fixes.log` | 2026-09-10 23:06:11 → 23:10:24 | **387 passed in 252.12 s** |
| `tools/` voll, **Versuch 3 = der Lieferlauf** (nach den Fixes, den Lesesuiten und dem Stempel 2026.09.10-1) | dieselbe Zeile | 2026-09-10 23:13:05 → 23:51:26 | **1 failed, 4843 passed, 14 skipped in 2299.29 s (0:38:19)**, rc 1 — der eine Rote ist `test_repo_hygiene::test_no_tracked_text_file_checks_out_with_crlf` (M12: die zwei Gen-4-Staging-Dateien des Hauptcheckouts, Zeile des Leads); 38 min gegen 1:54 am 2026-09-06 — derselbe Baum bis auf die zwei Fixes, der Unterschied ist die Host-Last |
| `.claude/hooks/test_gates.py` voll, Lauf 1 | `DELIVERY_RUN=TSK-0133 timeout 2400 python -B -m pytest .claude/hooks/test_gates.py -q -p no:cacheprovider` | 2026-09-10 23:52 → 2026-09-11 00:01:15 | **2 failed, 546 passed in 553.40 s (9:13)** — M13 (Gate-2-Test ohne `work`) und M14 (`_hole_prose` liest `source` als Pfad); beide in `.claude/hooks/test_gates.py` (Bereich dieses Auftrags) rot-zuerst geschlossen (Rig m23/m24), dabei M15 gefunden |
| `.claude/hooks/test_gates.py` voll, **Lauf 2 = die Gate-Abnahme** (die Lesesuite der geänderten Datei ist sie selbst, DEC-0063 (4)) | dieselbe Zeile → `project_memory/staging/TSK-0133/run-gates-suite.txt` | 2026-09-11 00:16:28 → 00:26:55 | **548 passed in 625.69 s (10:25)**, rc 0 |
| `tools/test_repo_hygiene.py` voll (liest den Nachtrag von M15 in `docs/reviews/`) | `timeout 900 python -B -m pytest tools/test_repo_hygiene.py -q` | 00:27:21 → 00:29:12 | 31 passed, **1 failed** — derselbe CRLF-Rote (M12, Zeile des Leads); die Zeiger-Leser (`-k "pointer or resolves"`, 6 Tests) und der Kernel-Sweep (30 Funde, 0 im Nachtrag) grün um 00:15:43–00:16:15 |

Nach dem Lieferlauf (Versuch 3) wurde **kein Kit-File** mehr angefasst (Stempel 2026.09.10-1 / 2026.09.06-1
stehen): geändert sind `.claude/hooks/test_gates.py` (M13/M14) und ein Nachtrag in
`docs/reviews/2026-09-02-tsk0107-office-duties-measurements.md` (M15) — beide außerhalb jedes
Kit-Hashes und außerhalb `tools/`; die Suiten, die sie lesen, sind oben in voller Länge gelaufen.

**Nachläufe der Prüfrunde 1 (2026-09-11, alle Läufe mit eigenem Log unter `_round-scratch/TSK-0133/`):**

| Lauf | Uhr | Ergebnis |
|---|---|---|
| gezielt: `tools/test_radar_trigger.py` (9), `test_review_procedure::test_no_lead_skill_keeps_its_own_copy_of_the_scaling_rule`, die zwei Gate-2-/Referenz-Tests | 01:19:01 → 01:22:33 | **12 passed** |
| Rig m23/m25/m26/m27 auf der nachgezogenen Kopie (`sync_copy`: 90 Dateien) | 01:22:33 → 01:23:02 | **4 × RED**, Log 28 Zeilen, `every row in log as expected: True` |
| Lesesuiten der geänderten Dateien, voll: `tools/test_repo_hygiene.py`, `tools/test_radar_trigger.py`, `tools/test_review_procedure.py` (`reading-suites-round1.log`) | 01:23 → 01:24:26 | **68 passed in 52.50 s** — darunter `test_no_tracked_text_file_checks_out_with_crlf` GRÜN: die zwei Gen-4-Dateien unter `staging/TSK-0126/` sind seit dem Lieferlauf normalisiert worden (`git ls-files --eol` 01:24:45: `i/lf w/lf`, 0 CRLF-Paare) — **nicht von dieser Runde**; wer die Zeile aus §13 gefahren hat, sagt dieses Protokoll nicht, es misst nur das Ergebnis. Damit ist M12 repariert und der eine Rote des Lieferlaufs hat seine volle Lesesuite grün |
| `bump_kit_version.py` | 01:24:26 | **unchanged ×3** (dev 2026.09.06-1, office 2026.09.10-1, research 2026.09.06-1) — kein Kit-File in der Nacharbeit |
| `tools/validate.py` / `ruff check .` | 01:24:26 / 01:23 | all structural checks passed / All checks passed |
| `.claude/hooks/test_gates.py` voll mit `DELIVERY_RUN=TSK-0133` (`run-gates-suite-round1.log`; LF-Kopie = `project_memory/staging/TSK-0133/run-gates-suite.txt`, die Evidenzdatei) | 01:24:49 → 01:35:38 | **548 passed in 648.04 s (10:48)**, rc 0 |

**Die drei Roten des Versuchs 2, mit Auflösung** (Fehlertexte im Log):

| Test | Befund | Auflösung |
|---|---|---|
| `tools/test_migrate.py::test_no_remedy_literal_this_repo_ships_names_a_place_inside_a_state_directory` | G5-3s `letter_draft.py` (Zeilen 77/359) nennt in zwei Abhilfe-Literalen `staging/<TSK-ID>/correspondence.yaml` — die DEC-0024-Regel (eine Abhilfe wählt den Ort im Zustandsverzeichnis nicht für den Leser); `test_migrate` stand in keiner Lesesuiten-Liste von G5-3 | beide Literale nennen das DING („in the task's own proposal area", `--proposal <the staged copy>`), so wie die Kernel-Meldungen „the generated index"; der Kernel (`documents.proposal_path`) erzwingt den Ort ohnehin. Kommentar mit Testname; Rig m21 (Pfad zurück) **rot**; die drei berührten Tests 6 passed (23:03:52–23:05:53) |
| `tools/test_parallel_streams.py::test_a_reference_skill_named_for_a_session_agent_is_named_by_a_text_it_reads` | `skills/correspondence` ist für den Büro-Manager (Sitzungsagent, bekommt keinen Dispatch-Header) deklariert, und kein Text, den er liest, buchstabiert die Codex-Route `.agents/skills/correspondence/SKILL.md` — G5-3 nannte `skills/correspondence/SKILL.md`; die Suite stand in G5-1s Liste, aber ohne G5-3s Datei im Baum | der Brief-Schritt des Büro-Manager-Skills nennt die Route in der Form der Humanizer-Zeile; Sektion neu gepinnt (23:05:54, eine Journalzeile); Rig m22 **rot** |
| `tools/test_repo_hygiene.py::test_no_tracked_text_file_checks_out_with_crlf` | `project_memory/staging/TSK-0126/run-full-suite.txt` und `run-gates-suite.txt` (Generation 4) liegen im Hauptcheckout mit CRLF auf der Platte, Index-Blob LF (`git ls-files --eol`: `i/lf w/crlf`); in EVD-0084s Lauf waren sie grün, in den Arbeitsbäumen der Ströme (frischer Checkout) ebenfalls — ein Artefakt der Arbeitskopie des Hauptcheckouts, das nach b7f282e entstand | **nicht von mir**: `project_memory/**` außer `staging/TSK-0133/` ist diesem Auftrag verboten. Die Zeile des Leads: `python tools/normalise_line_endings.py --apply` (schreibt nur Dateien zurück, deren normalisierte Bytes dem Blob gleichen — also genau diese zwei). Bis dahin ist dieser Test der EINE erklärte Rote des Lieferlaufs, mit Besitzer und Zeile |

Zwischen Versuch 1 und 2 wurde genau EINE Datei geändert: `tools/test_e2e.py` (§5 M9), kein Kit-File
— der Stempel 2026.09.06-1 steht. Host-Regel gehalten: immer nur EIN pytest (die Läufe dieser Runde
stehen mit Uhr in §2/§6/§7; der Lieferlauf startete, nachdem das Rig fertig war; `test_e2e` allein
lief erst nach dem Abbruch), jeder Lauf mit Frist, kein Last-Rig.

---

## 11. Die (g)-Tabelle

| | G5-2 ladders (TSK-0130) | G5-1 stock (TSK-0131) | G5-3 office (TSK-0132) | Merge (TSK-0133) |
|---|---|---|---|---|
| Stufe | Fable-Vorgänger (gestoppt, DEC-0081) → Opus 5 high (zwei Nachfolger nach der Pause) | Fable-Vorgänger → Opus 5 high (A), Opus 5 high (B nach der Pause) | Fable-Vorgänger → Opus 5 high | **Fable 5.1 high** (DEC-0081 (2); xhigh am Spawn nicht erreichbar) |
| Fable-Vorgänger | 21:14:59–22:08 (~53 min): Kernel-Leiter, drei `ladder.yaml`, Tests — behalten, 9 Befunde korrigiert (Protokoll 2 (a)–(i)) | 21:21–22:07 (0:46): Rigs, Bestandsläufe, AC-3/AC-4 — behalten, ein Defekt (Statusschreib-Form) | 21:11–21:57 (0:46): `test_office_package.py` 32 grün + 20-Mutationen-Rig — behalten | — |
| Runden | 1 Bericht + Nacharbeit 1 (DEC-0084-Messung) + DEC-0085-Erklärung + Handover-Runde; **3 Umsetzer** | 1 Bericht + 2 Nacharbeiten + Abschlussrunde + N21; **2 Umsetzer** (A, B) | 1 Bericht + 2 Nacharbeiten + Abschluss; 1 Umsetzer | 1 Bericht (dieses) |
| Verifikationen | FAIL / FAIL (R2-1 Zuschnitt) / Runde 3 = PR-0010 AC-1 auf dem gemergten Baum (Merge-Prüfer) | FAIL / FAIL / FAIL (enger) / FAIL ohne Blocker → N4-1..4 ohne fünfte Runde (DEC-0088 (c)), Merge-Prüfer misst N4-1/N4-2 | FAIL / FAIL / **PASS** | Merge-Prüfer (Opus) nach diesem Bericht |
| Token Umsetzer | Bericht ~465 k; Nacharbeit ~649 k; Erklärung ~782 k gesamt (Rundenlog-Lesungen); Nachfolger B ~265 k | A ~896 k (Lead-Zahl), B 287 k (eigener Zähler) | ~630 k (eigener Zähler, zwei Grenzen gelesen) | Zähler dieses Prozesses: 15,000 M → ~14,40 M beim Schreiben dieses Abschnitts (≈ 600 k; Endstand in §16) |
| Token Prüfer | R1 ~320 k, R2 ~471 k (Rundenlog) | **die Berichte 1–3 nennen keine Zahl**; der Rundenlog (Lead-Lesungen) sagt ~283 k / ~390 k / ~449 k; R4 ~212 k (Log) bzw. ~165 k (eigener Zähler des Prüfers) | ~300 k / ~409 k / ~452 k (Rundenlog) | — |
| Wandzeit gearbeitet / Spanne | Umsetzer 2: 22:12–00:57 + 07:26–17:09; Umsetzer 3: 17:15:54–19:09:12 (1:53, davon 1:15 Suite) / Spanne 21:14 → 19:13 | A ~14 h (davon ~5 h Suiten) 22:10 → 16:53; B 1:50 + N21 0:15 / Spanne 21:21 → 20:08 | 5:46 / 13:23 | Sitzung 1: 2026-09-06 20:14:11 → 2026-09-07 00:29 (Uhr; ~4 h 15, davon ~2 h 55 Suiten-/Rig-/Lieferlauf-Wartezeit, dazu der abgebrochene Versuch 1:13); Sitzung 2 (nach dem Wochenlimit): 2026-09-10 23:01:51 → §16 (Endstand); Spanne Spawn → Ende: §16 |
| Eigene Befunde am eigenen Bau | 9 gegen den Vorgänger, R3-1..R3-6 gegen die eigene Korrektur (darunter DISCLAIMER_RX fail-open, drei falsche Zitate, ein falsches Eigen-Urteil zurückgenommen) | Loch-Tabellen-Test, Zeigerindex, `stock_rollup` als Statusschreiber, `DEC_FIELDS`-Shadow, V1-Import-Kollision, zwei Rig-Artefakte, Scratch-Zeiger in Docstring, BUG-0270 | 8 am Vorgefundenen; 3 eigene (`tail`-rc als Pipe-Fehler, `_plant`-Anker, 118 gelöschte Zeilen) | drei eigene README-Sätze vom eigenen Leser verweigert (umformuliert); Rig-Artefakt (kopiertes `.git`) erkannt und ersetzt; Naht-6-Doppelforderung (M4) |
| Mutationen rot | Rig 1 19/19, Rig 2 31/32 (+1 Kontrolle) | 27 + Nacharbeiten + 12 (B) | 53 (+35 Prüfer) | **19/19 + 1 Kontrolle** (§6) |
| Löcher | H167–H173, H178, H182, H184, H186 | H174 (DUP), H175, H179, H180, H183, H185, H187 | H166, H176, H177, H181 | **H188** |

---

## 12. Zuschnitt-Befunde (für die Generation-5-Retrospektive)

| # | Befund | Quelle |
|---|---|---|
| Z1 | Der Lead schickte G5-2 die DEC-0085-Bauanweisung, während dessen Runde-2-Verifikation lief — ein Schreiber, eine Messung verletzt; R2-1 (Patch ≠ Baum) war die Folge | Rundenlog, TSK-0130 verify-round-2 |
| Z2 | **DEC-0089: der Lead maß „lief nie automatisch" an EINEM Log (Audit-Log des Repos, leere RemoteTrigger-Liste) statt an den Zeitstempeln der Artefakte** — die Freitags-Kadenz stand seit 2026-07-17 in `radar/`; zwei DECs (0084, 0085) und die Cloud-Erklärung von G5-2 wurden auf der falschen Prämisse gebaut, der Merge trägt die Korrektur | DEC-0089 (6), §4 |
| Z3 | Die Routine-API ist undokumentiert (Erklärung-dann-UI-Route) — durch Z2 gegenstandslos: der Mechanismus war lokal | Rundenlog 14:1x |
| Z4 | xhigh am Spawn nicht erreichbar (kein Effort-Parameter); DEC-0081 (2) nennt es für den Merge — dieser Umsetzer lief auf high | Rundenlog, BUG-0251 |
| Z5 | Die Fable-Vorgänger wurden nach Minuten gestoppt (DEC-0081), G5-3s hatte 46 min behaltene Arbeit; alle drei Nachfolger haben „Vorgefunden" gemessen statt neu gebaut | die drei Protokolle §0 |
| Z6 | PR-0010s Item verbot `report.py`, das AC-6 verlangte (BUG-0249) — im Merge geschlossen (Naht 9) | TSK-0130 verify-round-1 |
| Z7 | `update` nimmt `delivered_commit`/`evidence_refs` an einem PR still nicht an | Rundenlog 18:2x |
| Z8 | Zwei Uhr-Labels des Rundenlogs waren vor dem Lesen geschrieben (19:52/20:12) — vom Lead selbst benannt | Rundenlog |
| Z9 | Der Merge-Auftrag verlangte für Naht 6 „die Zeile mit ihrem Test" UND das Überleben des Filtertests, dessen Docstring die Zeile als noch offen führte — zwei Forderungen, die der Merge versöhnen musste (M4) | TSK-0133, TSK-0131 N18 |
| Z10 | Der veränderte Arbeitsbaum (Reindex) machte den Office-Patch mit `--3way` atomar unanwendbar — ein Patch, dessen Dateiliste eine live veränderte Datei trägt, braucht den Split vorab (M2) | §2 |
| Z11 | BUG-0270s Titel meint einen Test-Leser, liest sich aber wie das Kernel-Kommando (M5) | §5 |
| Z12 | Der Auftrag gab „~45–60 min" für die volle Suite und „every run with a timeout": auf dem Host des 2026-09-06 (85 % Fremdlast, gemessen) brauchte sie 1:54, und die vom Umsetzer nach der Auftragszahl gewählte Frist (90 min) hätte den Lauf getötet — ein Versuch verloren (§10). Eine Frist für die Vollsuite gehört aus der GEMESSENEN Dauer des letzten Laufs abgeleitet, mit Faktor, nie aus einer Auftragszahl | §10 |
| Z13 | Vier Kernel-Verträge der Ströme erreichten Suiten, die kein Strom in voller Länge fuhr — `test_e2e` (M9), `test_migrate`s DEC-0024-Regel (M10), `test_parallel_streams` (M11), die Gate-Suite (M13/M14): DEC-0080 Regel 2 („Leser des Prädikats greppen") hat die Leser über `capture`-RÜMPFE in fremden Suiten nicht erfasst, weil ein Rumpf kein Aufrufer des Prädikats ist; die Regel braucht den Grep über die AUFNAHME-Stellen des Typs (`"capture", "DEC"`, `capture("DEC"`, CLI-Rümpfe) dazu | §5, §10 |
| Z14 | Der Rundenlog des Leads las die Unterbrechung am 2026-09-07 als „Lauf läuft bei 81 %" — gemessen war der Lauf um 00:29:09 fertig (Endzeile im Log); der Neustart-Auftrag hätte den fertigen Lauf ohne die Vorgefunden-Messung wiederholt | Vorgefunden-Absatz |

---

## 13. Die zwei EVD-Zeilen für den Lead (state-relative Artefakt-Refs INNERHALB des Repos, kein Digest)

Nach dem PASS des Merge-Prüfers, aus dem Haupt-Checkout. **Die Laufprotokolle dieser Runde sind
LF** (Prüfrunde 1, B1: `run-full-suite.txt` trug 119 CRLF-Paare, `run-gates-suite.txt` 9 — pytests
Textstrom wird von der Shell-Umleitung `>> file` unter Windows in CRLF übersetzt; `lf_logs.py` hat
beide binär auf LF geschrieben, 119 → 0 und 9 → 0 Paare, kein anderes Byte verändert, gemessen
01:15; `normalise_line_endings.py --apply` kann das für eine UNVERFOLGTE Datei nicht, sie hat keinen
HEAD-Blob). **Die eine Zeile, die diesem Auftrag verboten war** (M12, die zwei Gen-4-Dateien unter
`staging/TSK-0126/`), ist inzwischen gefahren worden — nicht von dieser Runde; gemessen 01:24:45
(`i/lf w/lf`, 0 CRLF-Paare) — und `tools/test_repo_hygiene.py` lief danach in voller Länge grün
(32 passed innerhalb der 68 von 01:24:26, §10). Die zwei Zeilen stehen hier als das, was gemessen
ist; der Lead muss sie nicht mehr fahren:

```
python tools/normalise_line_endings.py --apply      # gefahren vor 01:23 (nicht von TSK-0133)
timeout 600 python -B -m pytest tools/test_repo_hygiene.py -q -p no:cacheprovider   # 32 passed, 01:24
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory evidence --kind test --result pass --related TSK-0133 --run-scope full --artifact-ref staging/TSK-0133/run-full-suite.txt --run-command "DELIVERY_RUN=TSK-0133 timeout 14400 python -B -m pytest tools/ -q -p no:cacheprovider" --summary "TSK-0133 generation-5 merge, delivery run of the full tools/ suite on the merged tree (stamps dev/research 2026.09.06-1, office 2026.09.10-1), 2026-09-10 23:13:05 -> 23:51:26: 4843 passed / 14 skipped / 1 failed in 2299.29 s. The one red, test_repo_hygiene::test_no_tracked_text_file_checks_out_with_crlf, named two generation-4 staging files of the main checkout (project_memory/staging/TSK-0126/run-*.txt) carrying CRLF in the working copy against an LF index blob -- outside the merge item's scope; they were normalised with tools/normalise_line_endings.py --apply after that run (measured LF 2026-09-11 01:24:45) and tools/test_repo_hygiene.py re-ran in full green (32 passed, 01:24:26, merge-protocol.md section 10). The first delivery attempt (2026-09-06 22:35 -> 00:29, 3 failed / 4841 passed) found two cross-stream defects, fixed red-first (merge-protocol.md section 5, M9-M11)"
PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory evidence --kind test --result pass --related TSK-0133 --run-scope full --artifact-ref staging/TSK-0133/run-gates-suite.txt --run-command "DELIVERY_RUN=TSK-0133 timeout 2400 python -B -m pytest .claude/hooks/test_gates.py -q -p no:cacheprovider" --summary "TSK-0133 generation-5 merge, the declared gate surface .claude/hooks/test_gates.py in full on the merged tree after verify round 1, 2026-09-11 01:24:49 -> 01:35:38: 548 passed / 0 failed in 648.04 s (the run of 00:16 -> 00:26 was 548 passed as well); the first gate run (00:01, 2 failed / 546 passed) found the DEC-0083 door in the gate-2 archive test and a hole-prose reader that read only migrated holes, both fixed red-first, and round 1 then pinned the gate-2 subject to DEC (merge-protocol.md section 5, M13-M15 and R1-B2)"
```

Beide Bedingungen des Summarys sind gemessen (§10, Nachläufe der Prüfrunde 1); die Zeilen tragen
keinen Platzhalter mehr.

---

## 14. Was auf den NUTZER wartet

1. **Push** von `feat/harness-v2` nach dem Commit des Leads (nie ohne sein Wort).
2. **Abnahme-Münzungen** `DELIVERED → ACCEPTED` (kind `acceptance`) für PR-0004..PR-0007; später dieselben für PR-0008..PR-0010 nach deren Lieferfreigaben.
3. **BUG-0069**: der gehostete CI-Lauf nach dem Push ist die Evidenz, die ihn schließt (EVD-0091 steht `fail` auf b7f282e; beide Reste sind repariert).
4. **Die Codex-Desktop-Task** (DEC-0089 (1)): in der Desktop-App anlegen — Name `codex-watcher`, Körper „Follow .claude/agents/codex-watcher.md exactly", samstags ~20:00, Ordner dieses Repo; der Lead trägt sie danach in `radar/routine.json` ein; `starts_itself` für die Codex-Hälfte wird wahr, sobald zwei Samstags-Berichte liegen. Die Cloud-Routinen von DEC-0085 sind NICHT anzulegen.
5. Die offene Frage aus G5-2: ob das Ablage-Paar (`records-clerk`/`filing-reviewer`) überhaupt klettern soll (`top: sonnet` in `office-team/ladder.yaml`).

---

## 15. Was bewusst NICHT geschlossen, aber benannt ist

| Als was | Was, und warum offen |
|---|---|
| Loch **BUG-0272/H188** | Gate-1-Über-Verweigerung (§5 M6); `.claude/hooks/` ist diesem Auftrag verboten |
| ohne Item, hier benannt | Gate 3 las `cd "…/TSK-0133" && git -C "C:/Offline Repos/v2-testbed/_round-scratch/TSK-0133/copy" add -A -- team-kits tools docs radar .claude README.md CLAUDE.md .gitattributes .gitignore NOTICES.md project_memory 2>&1 \| tail -2; …` als Unterkommando „repos/v2-testbed/_round-scratch/tsk-0133/copy" (Verweigerung 21:01); `git -C "<derselbe Pfad>" status --short`, `… add --dry-run -- README.md` und dieselbe Zeile mit `2>&1 \| tail -2` gingen rc 0 durch — der Mechanismus ist nicht isoliert, also kein Loch; der Lead entscheidet, ob er mit weiteren Proben verfolgt wird |
| ohne Item, hier benannt | `findings_beside_the_receipts_carrier` in `tools/test_migrate.py` fällt auf der heutigen Quittung nichts mehr; Filter + zehn Aufrufstellen zurückzubauen und den Runde-4-Test auf einen geplanten Fall zu stellen ist eine Aufräumzeile der nächsten Runde — kein Schutzloch (der neue Test hält die Zeile ohne den Filter) |
| unter BUG-0250/H168 | `session_status.py`s `{"lead": "opus", "worker": "sonnet", "light": "haiku"}` und die `light -> haiku`-Zeilen des Scaffolds (Scaffold verboten) — keine `<rung>-<effort>`-Schritte, außerhalb des Tripwire-Lesers, im Kartenkommentar gesagt |
| Abweichung von DEC-0089 (3), begründet | `starts_itself` prüft NICHT, ob die Task-Datei auf dem Host liegt (meldet es nur): ein CI-Klon ohne die Datei würde sonst wahre Sätze verweigern; der Eintrag des Leads plus die Kadenz der Berichte sind die Ableitung |
| Grenze der Messung | die Kadenz-Evidenz liest DATEINAMEN-Daten (Wochentag), nicht mtimes — die mtimes sind einmal von Hand gemessen und stehen im `source` des Records; ein Bericht, den jemand von Hand an einem Freitag startet, zählt mit (2026-09-04-claude, 00:30 am Folgetag geschrieben, zählt als siebter Freitag) |
| Vorlagen-Kommentar | „der Generator verweigert `light`/haiku" nennt DEC-0076 und keinen Testnamen — eine Nutzerprojekt-Datei, in der ein Repo-Testpfad nicht auflösbar wäre; der Test steht in Naht 5 |
| Titel BUG-0270 | zweideutig (§5 M5); nicht geändert, weil `observed`/`repro` den Leser eindeutig benennen |
| `dec-trigger-2.json` | trägt DEC-0085s Zustand; Weisung des Leads: nicht anfassen |
| BUG-0264/H182 | die vier Zeitplan-Sätze in `.claude/hooks/` (verboten) |

---

## 16. Uhr

**Sitzung 1 (2026-09-06/07):** Spawn 20:12; erste Lesung dieses Prozesses 20:14:11; erster Apply
20:19:36; letzte Kit-Änderung vor dem Stempel: `test_model_ladder.py`/Vorlagen 20:4x, Verfassungen
20:31 (Rekorde 20:55:59/20:56:05); Stempel 21:14:40; Lieferlauf Versuch 1 21:17:02 (abgebrochen
22:30:21); e2e-Fix 22:33; Versuch 2 22:35:17 → 00:29:09; Loch H188 21:18:05; Protokoll ab 21:20. Die
Sitzung endete danach am Wochenlimit der API.

**Sitzung 2 (2026-09-10/11):** Vorgefunden 23:01:51; Fixes M10/M11 23:03; Lesesuiten 23:06:11 →
23:10:24; Stempel office 2026.09.10-1 23:11:07; Rig komplett 23:11:10 → 23:12:33; Lieferlauf
Versuch 3 23:13:05 → 23:51:26; Gate-Suite Lauf 1 23:52 → 00:01:15; M13/M14/M15 00:03 → 00:16;
Gate-Suite Lauf 2 00:16:28 → 00:26:55; `test_repo_hygiene` voll 00:27:21 → 00:29:12; Endstand
dieses Protokolls **00:29:53** (`validate.py` und `ruff` grün zur selben Minute). Änderungssatz,
mit dem Befehl, damit die Zahl nachrechenbar ist (R1-P4: der Prüfer zählte 90 / 17 mit einem anderen
Schnitt — und der Prüfer hatte recht): `git status --short | grep -v "^.. project_memory/" | grep -v
"^?? project_memory/"` → **90 Zeilen**, davon **17** neue (`A`, ` A`, `??`). Meine frühere Zahl 83 / 15
kam aus `grep -v project_memory/`, das auch die sieben Kit-Vorlagen unter
`team-kits/*/templates/project_memory/` herauswarf (zwei davon neu: G5-3s `chart_of_accounts.yaml`,
`correspondence.yaml`) — ein Filter, der einen Pfad in der MITTE traf statt am Anfang; `git status
--short` insgesamt 283 Zeilen inkl. der Kernel-Schreibungen unter `project_memory/`.
`staging/TSK-0133/` trägt Protokoll, die zwei Laufprotokolle (LF), die Korrekturtexte BUG-0269/BUG-0272
und die Payloads H188/H189.

**Prüfrunde 1 (2026-09-11):** Bericht 00:33–01:09; Nacharbeit ab 01:14:26; Kernel-Schreibungen
01:17:22–01:17:30; die Läufe der Nacharbeit stehen in §10 (Runde-1-Nachläufe). **Token dieses Prozesses** (eigener Zähler,
15,000 M Budget): ~14,40 M am Ende von §11s erster Fassung, **~14,23 M beim Schreiben dieser
Zeile ≈ 770 k verbraucht** über beide Sitzungen (der Zähler zählt die ganze Sitzung, eine Lesung
ist eine Differenz mit Leseaufwand).
