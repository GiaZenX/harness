# TSK-0135 — Generation 6, das leichte Kit (PR-0011), Umsetzer-Protokoll

Basis: `feat/harness-v2` @ `5048c18` + TSK-0134's uncommittete Lieferung, Haupt-Checkout
`C:/Offline Repos/AgentAndSkills`. Ein Schreiber, ein Baum (`DEC-0087` (1)). Umsetzer: Fable 5.1,
effort high (`DEC-0088` (1)). Rot-zuerst-Messungen in
`C:/Offline Repos/v2-testbed/_round-scratch/TSK-0135/` (Kopie **ohne** `.git`, `rig/red_first.py`).
Kein Commit, kein Push, keine Installation in ein Nutzerprojekt. **Jede Uhrzeit ist vom schreibenden
Prozess gelesen** (`rig/log.py`, DEC-0094 (5)); das Rohprotokoll steht in Abschnitt 9.

Dieses Protokoll wächst mit der Runde (Limit-sicher, DEC-0093 (6)). Stand: **HALF** — Kernel-Vertrag,
Struktur-Gate, Checkpoint und Verteilungszeile gebaut und gemessen; die Textflächen, die Einstiegsdatei,
die Freigabe-Frage, die Auditor-Route, die Experiment-Arme und Rollout/Harvest kommen nach dem
Zwischencheck des Prüfers.

---

## 0. Der verworfene Weg, in einer Zeile (FR-0084)

**Verworfen:** die zwei neuen Auftragsfelder `rung`/`effort` als EIN Feldpaar zu führen, in das die
Lease ihre abgeleitete Antwort zurückschreibt (so stand der Kernel vor dieser Runde: `create_lease`
schrieb `task["rung"]`). **Grund, gemessen:** die Antwort würde zum Boden der nächsten Ableitung —
ein Auftrag, der nach einem FAIL einmal gestiegen ist, stiege beim nächsten Lease doppelt
(`start = max(floor, rung) + failed_runs`). Rig-Zeile M16 stellt genau diese Form wieder her und
`test_the_header_and_the_task_carry_the_rung_and_effort` wird rot: „the lease wrote its answer under
the ask's name". Deshalb zwei Namen für zwei Tatsachen: `rung`/`effort` = die Bitte des PM
(Planfeld, eingefroren außerhalb DRAFT), `lease_rung`/`lease_effort`/`lease_class` = was die Lease
ableitete (kernelgesetzt, dauerhaft, für Brief und Verteilung). **Was der kleinere Weg — gar kein Feld,
der PM gibt das Modell erst beim Spawn — NICHT gedeckt hätte:** die Bitte je Auftrag stünde nirgends
im Zustand; Brief und `check-scopes` könnten zwei parallele Aufträge nicht mit zwei Sprossen
nebeneinander zeigen (`DEC-0091` (3)), und die Ableitung könnte die Eskalation nicht „von dort, wo der
Auftrag beginnt" zählen.

Zweite Weiche, für das Struktur-Gate: **verworfen**, die Disjunktheit beim zweiten Bauer live zu
berechnen statt einen `check-scopes`-Datensatz zu verlangen. Die Live-Berechnung gibt es schon (die
Überlappungs-Verweigerung, stream D C-2) und sie lässt disjunkte Paare durch — genau die Gewohnheit,
die `DEC-0092` (2) messbar machen will: dass der PM VOR dem Schnitt gemessen hat. Der Datensatz ist
die Messung; ohne ihn ist die zweite Lease verweigert, mit ihm steht er auf der Lease
(`measured_disjoint`, PR-0011 AC-1 „evidence … on the lease").

---

## 0a. Je Kriterium die gemessene Zeile (Testname · Rot-zuerst-Mutation · Lauf)

| AC | gebaut | roter Test (Suite) | Mutation (Rig-Zeile) | Lauf / Messung |
|---|---|---|---|---|
| AC-1 | eine Bau-Lease je Ziel; zweite nur mit Datensatz, Datensatz auf der Lease; PM-Codeschreibzugriff verweigert | `test_a_second_build_lease_under_one_goal_needs_a_check_scopes_record` (light_kit) | M7, M18, M14b | Pilot-Rig 5.5: `lead_code_write rc 2` je Kit über die **registrierte Kette** `_gate.py guard_pm_scope.py gate_write_scope.py` — `gate_write_scope.py` allein gab rc 0 (P4 der Zielrunde: der AC-Text nennt das einzelne Gate, verweigert hat die Kette) |
| AC-2 | keine Teamgrößen-Frage in Einstieg, Lead-Skills, Verfassungen; DEC-0048-Ausweg bleibt | `test_hooks::test_no_entry_file_and_no_lead_text_asks_the_user_for_the_team_size` (+ Stolperdraht `test_the_team_size_reader_can_tell_a_question_from_the_escape`) | P3-AC2; **Nacharbeit B3:** R1-AC2-claude, R2-AC2-codex, R3-AC2-reader, R11/R12 (tote Alternativen entfernt, Träger gemessen) | rot auf dem alten Office-Satz, dann ersetzt; nach B3 ohne die nackte Alternative `derived\|Ableitung`: beide Zwillinge rot auf der „DERIVED"-Frage, der Leser rot, wenn die Alternative zurückkommt |
| AC-3 | `rung`/`effort` im TSK-Vertrag, `create-task` nimmt sie, `max()` mit Boden/Decke, Eskalation vom Start des Auftrags, Werte auf Lease/Brief/`check-scopes`, Vokabular-Verweigerung, Drei-Zeilen-Regel im PM-Text | `test_an_order_rung_lifts_the_start_and_the_climb_begins_there`, `…effort_lifts…caps_it`, `…above_the_roles_top…`, `…outside_the_ladder…refused`, `…create_task_command_accepts…check_scopes_shows…` | M1–M6, M10, M14a, V-B2, V-B4, V-B5, V-P7 | Pilot-Rig: sonnet/opus/fable bzw. office sonnet/opus/opus |
| AC-4 | Takt in PM-Skills und Verfassungen; Leser rot auf „Prüfer nach jeder Nacharbeit"; Rückschau-Regel mit Wanduhr gegen disjunkte Mengen | `test_no_kit_text_still_orders_a_verifier_after_every_rework` (+ Stolperdraht `test_the_cadence_reader_can_tell_an_order_from_its_negation`); `test_review_procedure` (Rückschau ein Text ×3) | P3-AC4; **Nacharbeit B4:** R4-AC4-not-optional, R5-AC4-pruefer, R6-AC4-negation-reader, R7-AC4-verifier-reader | 27 passed review_procedure; nach B4 verneint nur noch die verneinte ANORDNUNG: die Anordnung mit „NOT optional" und die in ASCII-Umschrift (`Pruefer`) sind rot, und der Stolperdraht wird rot, sobald die weite Verneinung oder die Umschrift-Alternative zurückgenommen wird |
| AC-5 | die Frage »Mit Langzeit-Gedächtnis … oder erstmal frei?« in beiden Einstiegsdateien; sofortige Installation, kleinstes Preset; kürzeres Interview | `test_hooks::test_both_entry_files_ask_the_same_first_contact_question_and_never_the_old_one` (Nacharbeit B5: beide Zwillinge tragen dieselbe Frage bis auf die Umschrift, die alte ist in beiden verboten); Pilot-Rig `smallest_preset` | **Nacharbeit B5:** R8-AC5-claude-old, R9-AC5-codex-old, R10-AC5-drift | Rig: solo/solo/core installiert; bis zur Zielrunde gab es für die Frage **keinen** Leser (B5: beide Zwillinge konnten auf die alte Frage zurückfallen, 1099 grün) |
| AC-6 | Brief, `invoices.json`, Arm A vorbereitet; Arm B **aufgebaut** (`rig/arm_b.py prepare`, fünf Schritte rc 0) und der Grund, warum er nicht unbeaufsichtigt läuft, **gemessen** statt behauptet | — (kein Test: eine Provider-Beobachtung, die dieses Repo nicht herleiten kann — `tools/provider_observations.json` sagt das im Kopfkommentar) | — | zwei `claude -p`-Läufe 08:11:08–08:12:21 und 08:14:02–08:14:33 (2.1.267, haiku): **0 `AskUserQuestion`**, `end_turn`, Abgabe in Prosa; Eintrag `headless_pm_stop_point`. **Lauf und Urteil sind Nutzerzeilen** (DEC-0093 (4)); dass der Arm hier gar nicht gefahren wird, ist `DEC-0095` (6) und löst den Satz des Items („run the kit arm") ab |
| AC-7 | deutsche Frage, Label-Tabelle beidseitig, Titel statt Id, Hash/Pfad in der Option, Gate vergleicht weiter | `test_every_approval_kind_has_one_plain_word_label…`, `test_no_approval_question_shows_an_english_enum_word…`, `test_hooks_v2::test_a_tampered_option_description_is_blocked_too` | P3-AC7a–d | Pilot-Rig: Routine-Frage deutsch. **Was NICHT aus der Frage verschwindet (P5), und warum:** der Marker `[APR-REQ:<32 hex>]` bleibt im Fragetext, weil `gate_approval` die Freigabefrage genau daran erkennt (`MARKER_RX`, aufgerufen über `_markers(q.get("question"))`, Zeile 143/155) — Hash und YAML-Pfad sind in die Option gewandert, die Anfrage-Id nicht. Der AC-Wortlaut („no hash / request id / YAML path in the question text") ist damit für die Id **nicht** erfüllt und kann es nicht sein, solange das Gate dort liest |
| AC-8 | `request-approval routine …`, `create-task --read-only`, `approvals.presents`, Hinweis nennt die Route, Texte ×3 | `test_the_auditor_runs_on_the_routine_route_from_the_command_line…`, `test_approvals_dispatch::test_minting_a_routine_on_a_live_root_leaves_its_approval_ref_alone` | P3-AC8a–c | Pilot-Rig je Kit: dispatch rc 0, `allowed_scope []`, `approval_ref` unverändert |
| AC-9 | von TSK-0134 geliefert; hier nur nachgemessen | `tools/test_radar_trigger.py` | — | 62 passed in der Batch model_ladder/pins/review/radar (04:07); im Volllauf |
| AC-10 | ein Bauer (Fable high), ein Zwischencheck (Opus), **eine Zielrunde (Opus, FAIL: 8 von 12)**, **eine Nacharbeit** (Opus high, DEC-0095); (g) in Abschnitt 7 | — | — | Abschnitt 7 (Zahlen gegen `generation-5-streams.md`) |
| AC-11 | Harvest gelaufen (0 Einträge); Update-Route auf einem Piloten gemessen (2026.09.06-1 → 2026.09.11-2) | — (Rig-Skripte) | — | 5.7, Rohprotokoll 04:46 |
| AC-12 | Struktur-Gate, Vier-Zeilen-Checkpoint (nie blockierend), Verteilungszeile, Rückschau-Urteil, Pilot-Rig bei jedem Stempel, kein Freitextfeld | `test_the_shipped_spawn_gate_prints_the_four_line_checkpoint…`, `test_the_mirror_still_exits_zero_when_its_audit_sink_is_gone`, `test_the_session_brief_carries_the_lease_distribution_line`, `test_no_spawn_or_lease_surface_carries_a_free_text_justification_field`, `test_the_pilot_rig_leases_three_orders_of_different_size_per_kit` | M7–M9b, M11a/b, M12a/b, M13, V-B1, V-B3b, V-B6, V-PRUNE, V-AC12 | Pilot-Rig 5.5 |

## 1. Dateitabelle (Stand HALF)

| Datei | Was |
|---|---|
| `team-kits/kernel/backlog_types.py` | `TSK_RUNG_FIELD`/`TSK_EFFORT_FIELD` (einmal buchstabiert), in `OPTIONAL_FIELDS["TSK"]` und `TSK_PLAN_FIELDS` (= „changeable while DRAFT", DEC-0091 (1)) |
| `team-kits/kernel/dispatch.py` | `RUNG_KEY`/`EFFORT_KEY` = die Vertragsnamen; `LEASE_RUNG_FIELD`/`LEASE_EFFORT_FIELD`/`LEASE_CLASS_FIELD`; `EFFORT_LEVELS`; `BUILD_CLASS`; `MEASURED_DISJOINT_KEY`; `order_tiers`, `rung_vocabulary` + `_reference_rungs` (Referenzzeile per Eigenschaft: die Durchreich-Zeile der Tabelle), `_assert_the_order_tiers_are_placeable` in `create_task`; `ladder_for_order`: `max()` über Boden und Bitte, `floor`/`start`/`order` in der Antwort, Effort-`max()` mit der höchsten deklarierten Stufe als Decke; `_valid_ladder`: `build`-Klasse Pflicht, Efforts im Vokabular; `running_leases`, `concurrent_builders`, `_assert_a_second_builder_was_measured_locked`; `create_lease` schreibt die drei `lease_*`-Felder aufs Item und `measured_disjoint` auf die Lease; `reflection_checkpoint` + `CHECKPOINT_QUESTION` |
| `team-kits/kernel/scopes.py` | `asks_line` (Bitte neben dem Auftrag), `order_digest`, `write_record`/`records`/`covering_record` (`tasks/scope-checks/<stamp>-<nonce>.check.yaml`), `goal_partition` (Zusammenhangskomponenten über Überlappungen); `check()` druckt Bitte und Datensatzpfad; Kopfkommentar korrigiert (was jetzt verweigert, wo) |
| `team-kits/kernel/layout.py` | `scopes._record_path` als kernelgeschriebener Teilbaum |
| `team-kits/kernel/report.py` | `DISTRIBUTION_WINDOW = 10`, `_leased_orders` (aktiv + Archiv), `_ran_to_done` (Automat), `lease_distribution`; Brief: `lease_distribution` + Zeile; Task-Zeile trägt Bitte und Lease-Antwort |
| `team-kits/kernel/schemas/session_brief.yaml` | Feld `lease_distribution` (Pflicht) |
| `team-kits/kernel/cli.py` | `create-task --rung RUNG --effort {low,medium,high,xhigh}` |
| `team-kits/{dev,office,research}-team/hooks/gate_dispatch.py` | `_mirror_the_builder_start`: nach `validate_dispatch` für eine BUILD-Lease die vier Zeilen als `hookSpecificOutput.additionalContext`, auditiert als Note, exit 0 auch wenn die Ableitung fällt; gespiegelt, sha256-Präfix `51667967173de368` in allen drei Kits |
| `tools/test_light_kit.py` | NEU, 14 Tests (Abschnitt 2) |
| `tools/test_ladder.py`, `tools/test_report.py`, `tools/test_schemas.py`, `tools/test_board.py`, `tools/test_approvals_dispatch.py` | Leser des geänderten Vertrags nachgezogen (Abschnitt 3) |
| `team-kits/*/VERSION` | Zwischenstempel `2026.09.11-1` (Hausregel 7: der Scaffold verweigerte einen Baum, der nicht zu seinem Stempel hasht — `test_reference_skills`, `test_research_chain`), `-2` nach den Texten, **Lieferstempel `2026.09.11-3`** nach der letzten Änderung (04:5x), vor dem Volllauf |

### 1a. Dateitabelle, Phase 3–6

| Datei | Was |
|---|---|
| `team-kits/kernel/approvals.py` | `KIND_LABELS`, `MANIFEST_LABELS`, `ROUTINE_KIND`, `kind_label`, `_item_target`, `item_title` im Request, `build_question` (deutscher Satz, Hash/Pfad in der Option), `_push_target_form` deutsch, `routine_subject_manifest` in `LINE_MANIFEST_BUILDERS`, `presents` + der Aufruf in `mint` |
| `team-kits/kernel/cli.py` | `request-approval`: Routine-Zweig (Item + Flags + `--expires-in-days`, Pflicht für routine), `--expires-in-days` für zeitbegrenzte Arten; `create-task --read-only` (oder `--allowed-scope`, nie keines) |
| `team-kits/kernel/dispatch.py` | Docstring der Routine-Route (Verdrängung aufgehoben), `reflection_checkpoint` Zeile (a) begrenzt und umformuliert (B6/P8), `floor_why` (P1), Effort-Ausnahme als Decke (B2), `_reference_rungs` mit `rungs:`-Ordnung (B4/B5) |
| `team-kits/kernel/scopes.py` | `covering_record` neuester Datensatz über das Paar (B3), Mikrosekunden im Namen, `_drop_records_about_closed_orders` |
| `team-kits/kernel/report.py` | `_check_dispatch_approval_presented` Docstring; Verteilung: `orders`, `_handed_back`, `runs_to_hand_back_per_rung` (P5/P6) |
| `team-kits/model_tiers.yaml` | `rungs: [sonnet, opus, fable]` (B4) |
| `team-kits/{dev,office,research}-team/hooks/_routine.py` | AUDIT_ROLE-Kommentar; Hinweis nennt die Route (gespiegelt; der ausgelieferte Spiegel-sha steht **einmal**, in 3a bei Fix (4) des Volllaufs 1 — der Wert hier war die Zwischenfassung und ist überholt) |
| `team-kits/{dev,office,research}-team/hooks/gate_dispatch.py` | Spiegel unter einem Wächter, Kontext vor der Note, `SystemExit` durchgereicht (B1); Docstring zeigt auf `hook_output_channels.pre_tool_use` (gespiegelt, sha `8732487ea375abd8`) |
| `team-kits/*/ladder.yaml` | Kommentar zu `effort`/`rung`-Ausnahmen (P2) |
| `team-kits/*/agents/project-auditor.md`, `skills/project-auditor/SKILL.md`, `constitution/AGENTS.md` | Routine-Route hat einen Produzenten; Rückschau-Frage 5; leichte Form + Takt in Schritt 6/7 und §11/§7 |
| `team-kits/{dev,research}-team/skills/project-manager/SKILL.md`, `office-team/skills/office-manager/SKILL.md`, `{dev,research}-team/skills/parallel-streams/SKILL.md` | Block „THE LIGHT FORM", Block „VERIFICATION AT THE GOAL", „derived, never asked", der Datensatz-Satz |
| `user/claude/CLAUDE.md`, `user/codex/AGENTS.md` | die neue Erstkontakt-Frage, kein Team-Interview, kleinstes Preset, kürzeres Interview |
| `tools/provider_observations.json` | `hook_output_channels.pre_tool_use` (Live-Messung P3) |
| `tools/lead_package_sizes.json`, `docs/reviews/phase0-disposition.md` | Paketgrößen aufgezeichnet, Journalzeile mit Begründung |
| `tools/light_kit_pilot.py` | NEU, der Pilot-Rig (DEC-0092 (6)) |
| `tools/test_light_kit.py` | 26 Tests (Vertrag, Ableitung, Vokabular, Struktur-Gate, Checkpoint, Verteilung, Rig, Takt-Leser, Freigabe-Frage, Auditor-Route, Freitext-Fläche) |
| `tools/test_hooks.py`, `test_hooks_v2.py`, `test_kernel.py`, `test_routine_feed.py`, `test_approvals_dispatch.py`, `test_ladder.py`, `test_report.py`, `test_schemas.py`, `test_board.py` | Leser nachgezogen (Abschnitte 3, 5) |
| `project_memory/staging/TSK-0135/experiment/*` | Brief, Daten, Arm A, Arm B |
| `project_memory/bugs/active/BUG-0277.yaml` | Kernel `capture BUG --hole` (H193) |

---

## 2. Rot-zuerst, Phase 1 (jede Zeile mit der Fehlerzeile des Schiedsrichters, DEC-0094 (10))

Rig: `rig/red_first.py` — kopiert den Baum ohne `.git`, mutiert **eine** Stelle (Bytes), fährt den
benannten Test in der Kopie, stellt die Datei aus dem Haupt-Checkout wieder her und prüft am Ende
Byte-Gleichheit. Lauf 2026-09-11 03:02:11 → 03:03:19 (Uhr vom Rig gelesen), M11b erneut 03:04:35.

| # | wiederhergestellter Defekt | roter Test | rc | Fehlerzeile |
|---|---|---|---|---|
| M1 | die Sprossen-Bitte hebt den Start nicht mehr (kein `max()`) | `test_an_order_rung_lifts_the_start_and_the_climb_begins_there` | 1 | `AssertionError: {'rung': 'sonnet', 'effort': 'high', … 'role_class': 'build', …}` |
| M2 | die Effort-Bitte hebt den Ziel-Effort nicht mehr | `test_an_order_effort_lifts_the_goals_effort_and_the_kits_highest_effort_caps_it` | 1 | `AssertionError: {'rung': 'sonnet', 'effort': 'high', 'kit': 'dev-like', …}` |
| M3 | die höchste Kit-Stufe deckelt nicht mehr (office xhigh) | dito | 1 | `AssertionError: {'rung': 'sonnet', 'effort': 'xhigh', 'kit': 'office-like', …}` |
| M4 | `top` deckelt eine Bitte über dem Rollen-Top nicht mehr | `test_an_order_rung_above_the_roles_top_is_capped_and_the_answer_says_so` | 1 | `AssertionError: {'rung': 'fable', …}` |
| M5 | `create_task` speichert eine Sprosse außerhalb der Leiter / einen Effort außerhalb des Vokabulars | `test_an_order_rung_outside_the_ladder_and_an_effort_outside_the_vocabulary_are_refused` | 1 | `Failed: DID NOT RAISE DispatchError` |
| M6 | das kitlose Projekt hat kein Vokabular (Referenzzeile nicht gelesen) | `test_a_kit_less_project_places_an_order_rung_against_the_reference_vocabulary` | 1 | `DispatchError: no scaffold record names a kit for this project and no model_tiers.yaml lies beside the kernel package …` |
| M7 | die zweite Bau-Lease unter einem Ziel wird ohne Datensatz erteilt | `test_a_second_build_lease_under_one_goal_needs_a_check_scopes_record` | 1 | `Failed: DID NOT RAISE DispatchError` |
| M8 | ein veralteter Datensatz (Auftrag seither umgeschnitten) deckt das Paar noch | `test_a_record_stops_covering_an_order_whose_scope_moved_since` | 1 | `AssertionError: assert {'checked_at': '2026-09-11T03:02:34', …}` (Datensatz gefunden statt None) |
| M9a | eine QA-Lease neben einem laufenden Bauer wird nach einem Datensatz gefragt (Klassenfilter weg) | `test_a_second_lease_of_another_class_or_under_another_goal_needs_no_record` | 1 | `DispatchError: TSK-0002 would be a SECOND builder under PR-0001 beside TSK-0001 …` |
| M9b | ein Bauer unter einem ANDEREN Ziel wird gefragt (Zielfilter weg) | dito | 1 | `DispatchError: TSK-0003 would be a SECOND builder under PR-0002 beside TSK-0001 …` |
| M10 | die Bitte ist auf einem READY-Auftrag änderbar (kein Planfeld) | `test_the_order_fields_are_the_contracts_and_frozen_with_the_plan` | 1 | `AssertionError: rung` |
| M11a | das Spawn-Gate druckt vor einem Bauer keinen Checkpoint | `test_the_shipped_spawn_gate_prints_the_four_line_checkpoint_and_never_blocks_on_it` | 1 | `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` (leerer stdout) |
| M11b | NIE-BLOCKIEREN: die Ableitung wirft | dito | 1 | `AssertionError: CHECKPOINT before builder TSK-0001 starts (DEC-0092 (3)): \| the checkpoint could not be derived (RuntimeError: boom); the spawn stands, the mirror does not \| assert '(a) …' in …` — **rc 0 des Gates hielt** (die erste Zusicherung des Tests), nur der Text fehlt |
| M12a | der Brief trägt keine Verteilung (striktes Schema verweigert) | `test_the_session_brief_carries_the_lease_distribution_line` | 1 | `kernel.schemas.SchemaError: session_brief failed schema validation:` |
| M12b | die Verteilung vergisst archivierte Aufträge | dito | 1 | `AssertionError: {'window': 10, 'leases': 3, …}` |
| M13 | `goal_partition` vereinigt überlappende Aufträge nicht (drei = drei Mengen) | `test_the_checkpoints_first_line_counts_the_goals_measured_disjoint_sets` | 1 | `AssertionError: assert [['TSK-0001']… ['TSK-0003']] == [['TSK-0001']…, 'TSK-0003']]` |
| M14a | `check-scopes` druckt keine Bitte neben dem Auftrag | `test_the_create_task_command_accepts_the_two_asks_and_check_scopes_shows_them_beside_the_order` | 1 | `AssertionError: matcher: … \| 2 open orders \| 12 files in the tree` |
| M14b | `check-scopes` hinterlässt keinen Datensatz | `test_a_second_build_lease_under_one_goal_needs_a_check_scopes_record` | 1 | `assert 0 == 1` |
| M15a | eine Deklaration ohne `build`-Klasse wird angenommen | `test_every_kit_ladder_declares_the_build_class_and_only_ordered_efforts` | 1 | `Failed: DID NOT RAISE DispatchError` |
| M15b | eine Deklaration mit Effort außerhalb der Ordnung wird angenommen | dito | 1 | `Failed: DID NOT RAISE DispatchError` |
| M16 | die Lease schreibt ihre Antwort unter den Namen der Bitte zurück (Doppel-Aufstiegsform) | `test_the_header_and_the_task_carry_the_rung_and_effort` (test_ladder) | 1 | `AssertionError: the lease wrote its answer under the ask's name: {'id': 'TSK-0001', …}` |
| M17 | die Brief-Zeile lässt die Lease-Antwort weg | `test_the_session_brief_shows_the_rung_and_effort_a_lease_wrote_on_the_task` (test_report) | 1 | `KeyError: 'lease_rung'` |
| M18 | die Lease des zugelassenen zweiten Bauers nennt keinen Datensatz (AC-1 „on the lease") | `test_a_second_build_lease_under_one_goal_needs_a_check_scopes_record` | 1 | `KeyError: 'measured_disjoint'` |

Die Suite `tools/test_light_kit.py` ist die Suite dieser Zeilen; drei weitere Zeilen liegen in
`test_ladder.py` und `test_report.py`.

### 2a. Die Befunde des Zwischenchecks (`verify-half.md`), jeder mit Fix und roter Zeile

Rig-Lauf 04:05:53 → 04:06:29 (`rig/red_first-20260911-040551.log.json`); die Phase-1-Zeilen liefen davor
erneut (04:04–04:05, alle rot wie oben; M8/M14b nach dem B3-/Prune-Umbau neu verankert).

| # | Befund | Fix | roter Test | rc | Fehlerzeile |
|---|---|---|---|---|---|
| B1 | Spiegel-Rumpf außerhalb des `try`: werfender Audit-Sink → rc 2 bei verbrauchtem Claim | ganzer Rumpf unter einem Wächter; Kontext VOR der Note geschrieben; `SystemExit` durchgereicht | `test_the_mirror_still_exits_zero_when_its_audit_sink_is_gone` (kopierte Hooks, `record_note` wirft, Gate als Prozess) | 1 | `AssertionError: (2, '[team-kit gate_dispatch] internal error (RuntimeError: the audit sink is gone) … refused rather than passed …') \| assert 2 == 0` |
| B2 | Effort-Ausnahme (Ablagesockel) von einer Bitte gehoben | Ausnahme ist Boden UND Decke: `ceiling = exception effort`; `why` „the order asks high, but the exception fixes low (DEC-0047)" | `test_the_filing_pair_starts_on_its_pin_at_low_effort_and_still_climbs` (+ Ask-Fall) | 1 | `AssertionError: ('records-clerk', {'rung': 'sonnet', 'effort': 'high', …}) \| assert 'high' == 'low'` |
| B3 | `covering_record` nahm den neuesten DISJOINT-Datensatz statt den neuesten über das Paar | neuester Datensatz, der das Paar nennt, allein wird befragt | `test_a_newer_overlap_record_revokes_an_older_disjoint_verdict` | 1 | `AssertionError: assert {'checked_at': '2026-09-11T04:06:10', …} is None` |
| B3 (Rand) | Datensatzname hatte Sekundenauflösung; zwei Läufe in einer Sekunde ordneten sich nach dem Nonce | Name trägt Mikrosekunden | dito (fiel beim ersten Lauf des neuen Tests: der ältere Datensatz sortierte vorn) | — | gemessen am 04:00-Lauf, danach grün |
| B4 | kitloses Vokabular kam hoch→niedrig | `model_tiers.yaml` trägt `rungs: [sonnet, opus, fable]`; `_reference_rungs` liest die Ordnung dort und verweigert eine Zeile, die nicht genau die Durchreich-Zeile nennt | `test_the_reference_row_is_found_by_its_property_and_not_by_a_name` (Ordnung gegen jede Kit-Leiter) | 1 | `assert ['fable', 'opus', 'sonnet'] == ['sonnet', 'opus', 'fable']` |
| B5 | Eigenschafts-Stolperdraht konnte nicht rot werden | derselbe Test mit SYNTHETISCHEN Tabellen: Durchreich-Zeile unter `acme:`, `claude:` übersetzt; null / zwei Zeilen; falsche `rungs:`-Zeile | dito, Mutation = `provider == "claude"` (N3b des Prüfers) | 1 | `Failed: DID NOT RAISE DispatchError` (die Namensvariante nimmt claudes übersetzende Zeile) |
| B6 | Zeile (a) unbegrenzt | > `PATHS_SHOWN` Mengen: „… and N more sets"; > `PATHS_SHOWN` offene Aufträge: nur Zahl | `test_the_checkpoints_first_line_counts_the_goals_measured_disjoint_sets` (+ 13 Aufträge) | 1 | `AssertionError: (a) this goal splits into 12 disjoint sets among 13 open order(s) …: TSK-0001; …; ... and 2 more sets \| assert False` |
| P7 | Doppel-Aufstieg stand nirgends als Test | Sechs-Sprossen-Leiter, ein FAIL je Lease | `test_the_two_name_split_is_what_keeps_a_climbed_order_from_climbing_twice` (Mutation M16) | 1 | `AssertionError: ['r1', 'r2', 'r4', 'r6'] \| assert … == ['r1', 'r2', 'r3', 'r4']` |
| offen: scope-checks-Wachstum | jeder Lauf eine Datei | `_drop_records_about_closed_orders`: Datensätze, deren Aufträge alle geschlossen sind, fallen beim nächsten Lauf | `test_a_check_scopes_record_about_closed_orders_is_dropped_at_the_next_run` | 1 | `AssertionError: ['…\\scope-checks\\2026-09-11T040625.146308-204e2a40.check.yaml'] …` |
| offen: AC-12 Freitext-Leser | kein struktureller Test | `test_no_spawn_or_lease_surface_carries_a_free_text_justification_field`: Gate-gelesene `tool_input`-Schlüssel (AST), Header-Schlüssel, Signaturen `create_lease`/`validate_dispatch`, Pflichtoptionen von `create-task` gegen den Vertrag, Pflichtfelder des TSK — geschlossene Flächen | dito, Mutation = `--why` Pflichtoption | 1 | `AssertionError: required options that feed no contract field: [['--why']]` |
| P1 | `floor_why` widersprach sich | „the exception sets the floor" | — (Prosa) | | |
| P2 | Leiter-Kommentare „fixed" | drei `ladder.yaml`: `effort` = Boden UND Decke; `rung` = Boden, den eine Bitte heben darf | — (Prosa; `test_model_ladder` liest die Deklarationen) | | |
| P3 | PreToolUse-Kanal mit PostToolUse-Messung belegt | LIVE GEMESSEN 03:55:27 (claude 2.1.258, Scratch `probe-pre-context`, `-p`): Antwort `hello` / `PRE-CONTEXT-MARKER-9b7d` — `additionalContext` erreicht das Modell; `systemMessage`-Marker nicht wiederholt; eingetragen als `hook_output_channels.pre_tool_use` in `tools/provider_observations.json`; Docstring zeigt dorthin | | | |
| P4 | „the PM has to have run" | „somebody has to have run … WHO ran it is not read and cannot be: `check-scopes` ist kein Ordering-Kommando" | | | |
| P5/P6 | „leases" / „passed" | Aufträge nach letzter Lease (`orders`), „runs to hand-back" (Schwelle SUBMITTED = abgegeben, nicht bestanden); Schlüssel umbenannt, Brief-Fixture nachgezogen | `test_the_session_brief_carries_the_lease_distribution_line` | | |
| P8 | „measured-disjoint" für eine Live-Partition | „N disjoint sets (computed now; a second builder still needs a check-scopes record)" | | | |

Verworfen aus dem Rig: eine Zeile `"disjoint" in named` blieb GRÜN (rc 0, 04:06) — ein Datensatz nennt ein
Paar nur unter einem Schlüssel, die Mutation stellt keinen Defekt her (`DEC-0070`).

### 2b. Rot-zuerst, Phase 3 (Freigabe-Frage, Auditor-Route, Texte)

Lauf 04:48:21 → 04:48:50 (`rig/red_first-20260911-044819.log.json`), P3-AC2 erneut 04:50:49 nach der
Korrektur des Lesers; **Gesamtlauf aller 41 Zeilen** 04:52–04:55 (`rig/red_first-20260911-045*.log.json`):
alle rc 1.

| # | wiederhergestellter Defekt | roter Test | rc | Fehlerzeile |
|---|---|---|---|---|
| P3-AC7a | das Enum-Wort steht wieder im Satz | `test_no_approval_question_shows_an_english_enum_word_a_hash_or_a_path` | 1 | `AssertionError: Freigabe erbeten: analysis für [erwartetes Ergebnis: …] … assert False` |
| P3-AC7b | der Hash-Präfix steht wieder im Satz | dito | 1 | `AssertionError: … (sha256 deadbeefdead). \| assert ('approvals/pending' not in …` |
| P3-AC7c | eine Art ohne Label (Stolperdraht-Ende eins) | `test_every_approval_kind_has_one_plain_word_label_and_no_label_is_orphaned` | 1 | `AssertionError: {'hole_exception'}` |
| P3-AC7d | das Gate vergleicht die Options-Beschreibung nicht mehr (wohin Hash und Pfad zogen) | `tools/test_hooks_v2.py::test_a_tampered_option_description_is_blocked_too` | 1 | `assert (0 == 2)` — das Gate ließ die manipulierte Beschreibung durch |
| P3-AC8a | die Routine-Prägung verdrängt wieder die präsentierte Freigabe der Wurzel | `test_minting_a_routine_on_a_live_root_leaves_its_approval_ref_alone` | 1 | `AssertionError: the routine mint moved approval_ref \| assert 'APR-0002' == 'APR-0001'` |
| P3-AC8b | `request-approval` ohne Routine-Zweig | `test_the_auditor_runs_on_the_routine_route_from_the_command_line_without_a_writable_scope` | 1 | `a routine approval has no item -- its subject is role, scope, trigger, cadence. Remedy: drop 'PR-0001'` |
| P3-AC8c | `create-task` nimmt einen Auftrag ohne Scope und ohne `--read-only` | dito | 1 | `assert (0 != 0) … stdout='TSK-0001 DRAFT (project-auditor)'` |
| P3-AC2 | der Office-Lead fragt wieder nach der Teamgröße | `tools/test_hooks.py::test_no_entry_file_and_no_lead_text_asks_the_user_for_the_team_size` | 1 (erst 0!) | `AssertionError: these texts still ask the user for the team size: {'…office-manager/SKILL.md': ['Preset confirm (recommend `core` first … ask which TEAM SIZE the user wants …']}` — **beim ersten Lauf GRÜN**: der Leser prüfte die Verneinung je Block und der mutierte Block trug noch „No team-size question to the user"; jetzt je Satz, mit einem gemischten Fixtur-Block im Stolperdraht-Test |
| P3-AC4 | ein Kit-Text ordnet den Prüfer nach jeder Nacharbeit an | `test_no_kit_text_still_orders_a_verifier_after_every_rework` | 1 | `AssertionError: {'…project-manager/SKILL.md': ['After every rework the verifier runs the whole package again.']}` |

Eigener Befund dieses Lesers: nach dem Kürzen der Verfassungen wurde er rot auf „carries no cadence at
the goal", weil „one\n   rework" umbrach — der Test prüfte den Rohtext; jetzt geglättet.

---

## 3. Läufe (welche und warum), Phase 1

Gate 5 lebt; kein Lauf über die volle Fläche vor dem Lieferstempel. Ein pytest zur Zeit, jeder mit
Zeitgrenze (`rig/run_suites.py`, Logs `rig/suites-*.log.json`).

| Lauf | warum | Ergebnis |
|---|---|---|
| `test_ladder.py` | Suite der Leiter (Ableitung geändert) | 35 passed, 16.5 s |
| `test_light_kit.py` | Suite der neuen Regeln | 14 passed, 8.8 s |
| `test_report.py -k "session_brief or distribution"` | Brief + Verteilung | 5 passed |
| `test_parallel_scopes.py` + `test_parallel_streams.py` | Leser von `scopes` und der Lease-Regeln | 45 passed, 23 s |
| `test_schemas.py` + `test_backlog_types.py` | Schema des Briefs (neues Pflichtfeld), TSK-Vertrag | 80 passed (nach Nachziehen des handgebauten Briefs in `make_brief`) |
| `test_kernel.py`, `test_state.py`, `test_model_ladder.py`, `test_e2e.py` | Capture-Stellen des TSK-Typs, `kernel_written_subtrees`, Leiter-Texte, Ende-zu-Ende | 131 / 61 / 12 / 20 passed |
| `test_review_procedure.py`, `test_role_contracts.py`, `test_staging_cli.py` | Rollen-/Verfassungsleser, CLI-Oberfläche | 27 / 30 / 98 passed |
| `test_board.py` | Schreiber ohne Index-Regeneration | 1 rot → `scopes.write_record` mit Grund in `_WRITERS_THE_BOARD_DOES_NOT_RENDER` → 77 passed |
| `test_approvals_dispatch.py` | Status-Schreib-Leser, Architekt-Schritt | 2 rot → (1) Leser folgt einem Alias eines importierten Vertragskonstanten (ein Hop, Stolperdraht beidseitig erweitert), (2) der Architekt-Schritt-Test least zwei Bauer unter einem Ziel und fährt jetzt `check-scopes` davor → 197 passed, 82 s |
| `test_reference_skills.py`, `test_research_chain.py` | Scaffold-Läufe | 2 rot + 10 Fehler VOR dem Stempel (Scaffold: „does not hash to the `content:` in its own VERSION"), nach `bump_kit_version.py` 18 / 10 passed |

| `test_migrate.py -k "brief or kernel_written or subtree"` | Leser des Briefs / der kernelgeschriebenen Teilbäume | 1 passed |
| `test_hooks_v2.py -k "dispatch or spawn or chain or lease"` | die Gate-Kette, der Spawn-Pfad | 62 passed, 32 s |
| `test_hooks_v2.py -k preamble` | `gate_dispatch.py` hat einen Import hinter der Präambel bekommen | 10 passed |
| `test_hooks.py -k "shared_kit_files_identical or registration_names_a_window or leaves_no_bytecode or command_surface or entry_points_surface or every_kernel_command_an_entry_gate or every_hook_an_entry_gate or kernel_bridge_is_staged"` | Spiegelregel, Registrierungen, Kommandofläche | 8 passed |
| `test_shortening_net.py`, `test_context_budget.py`, `test_kitupdate.py` | Pfad-Sweep, Kontextbudget des Briefs, Update-Route (Stempel) | 36 / 42 / 86 passed + 1 skipped (240 s) |
| `python -B tools/validate.py` | Lieferkriterium (nach dem Zwischenstempel) | all structural checks passed |
| `python -m ruff check .` | Lieferkriterium | All checks passed |

Callers der bewegten Prädikate (`DEC-0080` Regel 2, `DEC-0094` (7)): `ladder_for_order`/`create_lease`
werden von `cli.py`, `checkpoints.py`, `report.py`, `state.py` (Transitionen), `kitupdate.py`, den
Hooks `gate_dispatch`/`gate_approval`/`gate_write_scope`/`_kernel` und den Suiten `test_ladder`,
`test_light_kit`, `test_parallel_streams`, `test_approvals_dispatch`, `test_kernel`, `test_e2e`,
`test_board`, `test_staging_cli`, `test_reference_skills`, `test_research_chain`, `test_hooks`,
`test_hooks_v2`, `test_migrate`, `test_kitupdate`, `test_context_budget`, `test_shortening_net`
gelesen; die TSK-Capture-Rümpfe stehen in `test_kernel`, `test_state`, `test_approvals_dispatch`,
`test_hooks`, `test_e2e`, `test_board`, `test_report`, `test_parallel_*`, `test_migrate`,
`test_plan_diagram`, `test_migrate_holes`, `test_shortening_net`, `test_staging_cli`. Alle bis auf die
drei noch offenen Batches sind gelaufen.

---

### 3a. Die Volläufe (DEC-0080 (5): Stempel, dann EIN Volllauf mit dem Lieferpräfix)

| Lauf | Stempel | Zeit | Ergebnis |
|---|---|---|---|
| `DELIVERY_RUN=TSK-0135 python -B -m pytest tools/ -q -p no:cacheprovider` (1) | 2026.09.11-3 | 04:55:5x → 05:35:29, 2371.94 s (39:31), Zeitgrenze 6840 s (2280 s × 3) | **8 failed / 4874 passed / 14 skipped** |
| dieselbe Zeile (2) — **der Lieferlauf** | 2026.09.11-4 | 05:46 → 06:26:07, 2395.10 s (39:55), Zeitgrenze 4744 s (2372 s × 2) | **4882 passed / 14 skipped / 0 failed, rc 0** (`full-tools-run-2.log`) |
| `DELIVERY_RUN=TSK-0135 python -B -m pytest .claude/hooks/test_gates.py -q -p no:cacheprovider` | 2026.09.11-4 | 06:26 → 06:39:30, 757.25 s (12:37), Zeitgrenze 4140 s (1380 s × 3) | **548 passed, rc 0** (`full-gates-run-1.log`) |
| `python -m ruff check .` / `python -B tools/validate.py` / `python tools/bump_kit_version.py` | 2026.09.11-4 | nach dem Stempel, vor Lauf 2 | All checks passed / all structural checks passed / dreimal `unchanged (2026.09.11-4)` nach den Läufen |

Die Logs liegen LF-geschrieben neben diesem Protokoll (`stage_logs.py`: Bytes gelesen, CR/CRLF → LF,
je Datei „CR left: 0"): `full-tools-run-1.log`, `full-tools-run-2.log`, `full-gates-run-1.log`,
`protocol-log.md`, `light_kit_pilot.log.json`, `update_route.log.json` und die drei Rot-zuerst-Logs:

- `red_first-20260911-045313.log.json` — **der Gesamtlauf: 41 Zeilen, jede rc 1**, 04:53:15–04:55:21
  (M1–M18, V-B1…V-AC12, P3-AC7a–d, P3-AC8a–c, P3-AC2, P3-AC4). Bis zur Zielrunde nannte diese Stelle
  die Datei daneben, die nur **eine** Zeile trägt (P1 der Zielrunde).
- `red_first-20260911-045047.log.json` — der Einzel-Nachlauf der Zeile P3-AC2 (1 Zeile, 04:50:49–04:50:53).
- `red_first_rework-20260911-082057.log.json` — die **Nacharbeit**: 10 Zeilen R1…R10, jede rc 1,
  08:21:18–08:25:30, in einer eigenen Kopie (`rework/`), damit der Baum der Zielrunde unberührt bleibt.
- `red_first_rework-20260911-084034.log.json` — zwei Zeilen nach (R11, R12, beide rc 1, 08:40:36–08:40:44):
  aus der Negation des AC-2-Lesers sind drei Alternativen verschwunden, weil sie nichts entscheiden
  konnten (`never asked` und `NEVER ask` sind von `never ask` unter IGNORECASE schon getroffen). Die
  zwei Zeilen messen, dass die **verbliebene** Alternative beide ausgelieferten Wortlaute trägt: ohne
  sie ist der Stolperdraht rot (`NEVER ask the team size …`) **und** der Lauf über die ausgelieferten
  Texte (`DERIVED, never asked …` in der dev-Verfassung).

Dazu unter `experiment/` die Messung zu AC-6: `prepare.log.json` (Aufbau Arm B, fünf Schritte rc 0)
und `probe-20260911-081108.summary.json` / `probe-20260911-081402.summary.json` (die beiden
`claude -p`-Läufe mit Rohstrom-Auszug; die Rohströme selbst bleiben im Rundenverzeichnis).

Die acht Roten von Lauf 1, jede ein Befund, jede rot-zuerst durch den Lauf selbst und dann grün in
ihrer Suite:

| Test | Befund | Fix |
|---|---|---|
| `test_disposition::test_every_code_citation_resolves_in_the_file_it_names` | `docs/reviews/phase0-disposition.md` zitierte dreimal den umbenannten Test `…takes_its_approval_ref` | die drei historischen Zeilen zitieren den neuen Namen und sagen, dass er seit Gen 6 das Gegenteil misst |
| `test_hooks::test_every_hook_an_entry_gate_names_is_shipped_by_every_kit_in_that_blocks_scope` | mein Preset-Absatz nannte `office-team` im selben Block wie `gate_memory_complete`, das office nicht liefert | „`core` for the office kit" ohne Kit-Schlüssel (beide Einstiegsdateien) |
| `test_hooks::test_kit_names_a_root_item_exactly_when_the_kernel_gives_it_one` | Research-Texte nannten `PR-0011` (Wurzeltyp RQ) | „since generation 6 (BUG-0266)" in Definitionen, Skills, Verfassungen ×3 |
| `test_parallel_streams::test_no_text_that_describes_the_audited_role_states_the_cadence_the_code_owns` | die Routenzeile in der Verfassung sagte `--cadence weekly` — der Takt gehört `_routine.audit_period_id` | `--cadence <how often>` in Verfassungen, Auditor-Skills, Hook-Hinweis (gespiegelt, sha `1e6b941e1f45ab2a`) |
| `test_repo_hygiene::test_every_test_pointer_this_repo_writes_resolves` | fünf Kernel-Kommentare zitierten `tools/test_ladder.py::…` für Tests, die in `test_light_kit.py` liegen | Zitate korrigiert (`backlog_types.py`, `dispatch.py` ×4) |
| `test_repo_hygiene::test_every_hole_is_one_index_row_one_prose_file_and_one_item` | H193 ohne Indexzeile | `migrate-holes --reindex` durch den Kernel (183 Löcher) — das Item nannte den Reindex als Schritt des Leads „after your last"; mein letztes Loch war erfasst, also gefahren, damit der Lieferlauf misst, was geliefert wird |
| `test_report::test_a_root_presenting_a_non_dispatching_approval_is_reported` | der Test erzeugte den verdrängten Verweis über `mint`, das ihn seit `approvals.presents` nicht mehr erzeugt | der Test schreibt den Verweis von Hand am Kernel vorbei (die Form, die der Validator weiter melden muss) und sichert zu, dass die Prägung ihn nicht bewegt |
| `test_shortening_net::test_no_section_of_a_pinned_instruction_file_disappears_unnoticed` | 14 gepinnte Abschnitte geändert (Schritt 5a/4a, §11/§7/§13, PM-Skill-Abschnitte) | `pin_constitution_sections.py --write --note` mit Begründung (Journal in `phase0-disposition.md`) |

Dazu die Lead-Paketgrößen zweimal mit Begründung aufgezeichnet (`+1303/+1224/+1401 B` nach dem
Kürzen der Verfassungsblöcke, dann `+4 B`), und der Stolperdraht des AC-4-Lesers nach dem Kürzen
(Zeilenumbruch in „one rework"; der Test glättet jetzt).

## 4. Was HALF deckte, gegen die Kriterien (Stand des Zwischenchecks; der Rest steht in 0a und 5)

- **AC-3** (Stufen je Auftrag): Vertrag, `create-task`, `max()` mit Boden und Decke, Eskalation vom
  Startpunkt des Auftrags, beide Werte auf Lease (`rung`/`effort`), im Brief (`rung`/`effort` = Bitte,
  `lease_rung`/`lease_effort` = Antwort) und in `check-scopes` neben dem Auftrag; Vokabular-Verweigerung
  bei Erstellung UND Lease. Offen für Phase 2: der PM-Pflichttext (Drei-Zeilen-Regel, „nie nach Stufen
  fragen").
- **AC-1 / AC-12 Verweigerung**: zweite Bau-Lease unter einem Ziel nur mit Datensatz, Datensatz auf
  der Lease; rot-zuerst M7/M8/M9a/M9b/M14b/M18. Nicht gebaut und benannt: das Gate greift nur, wenn
  eine Leiter die Klasse `build` liefert — das kitlose Projekt (dieses Repo) bleibt außerhalb
  (`test_a_kit_less_project_is_outside_the_second_builder_rule`), und es liest nur den GLEICHEN
  `product_requirement`; zwei Bauer unter zwei Zielen sind DEC-0087 (2)'s erlaubte Form.
- **AC-12 Checkpoint**: die vier Zeilen + Frage, gedruckt vom ausgelieferten `gate_dispatch.py` als
  `additionalContext` auf dem erlaubten Aufruf, nur für BUILD-Leases, nie blockierend (M11b).
- **AC-12 / DEC-0092 (4) Verteilungszeile**: im Brief, aus aktiven + archivierten Aufträgen, Fenster 10;
  „runs to done" = FAILED-Läufe + 1 (kein Zustandsfeld zählt Prüferrunden — im Docstring gesagt).
- Nicht in HALF: AC-2, AC-4 Texte, AC-5, AC-6, AC-7, AC-8, AC-10 (g)-Tabelle, AC-11, Pilot-Rig,
  Rückschau-Regel-Text.

---

## 5. Phase 3–6 (nach dem Zwischencheck): Routen, Texte, Einstieg, Rig, Experiment, Rollout

### 5.1 AC-7 — die Freigabe-Frage auf Deutsch (BUG-0271, BUG-0073)

`kernel/approvals.py`: `KIND_LABELS` (eine Tabelle neben `APR_KINDS`, beidseitiger Stolperdraht
`test_every_approval_kind_has_one_plain_word_label_and_no_label_is_orphaned`), `MANIFEST_LABELS`
für die generisch gerenderten Manifest-Schlüssel (Routine, Analyse, Kit-Update), `item_title` wird
beim Anlegen der Anfrage eingefroren (deterministisch aus dem Request, wie das Gate es verlangt),
`build_question` schreibt `Freigabe erbeten: <Art in Klartext> für „<Titel>“ (<Id>) (Revision n).
[APR-REQ:<id>]` — der Marker bleibt, weil `gate_approval.MARKER_RX` ihn aus der Frage liest; Hash
und Pfad stehen in der Beschreibung der Freigeben-Option, die das Gate weiterhin Zeichen für
Zeichen vergleicht. Das Push-Formular ist deutsch. Der Wert-Sprach-Regeltext von BUG-0073 bleibt
(`test_every_kit_lead_is_told_which_language_an_approval_value_is_written_in` grün).

| Messung | Test | Ergebnis |
|---|---|---|
| jede Art gerendert: kein Enum-Wort, kein Hash außer hinter „Prüfsumme", kein Pfad im Satz; Hash + Pfad in der Option | `test_no_approval_question_shows_an_english_enum_word_a_hash_or_a_path` | grün; rot ohne Label-Tabelle / ohne den Umzug |
| manipulierte Options-Beschreibung verweigert (PreToolUse rc 2 „option 0 description differs"; PostToolUse prägt nichts) | `tools/test_hooks_v2.py::test_a_tampered_option_description_is_blocked_too` | grün |
| Routine-Frage nennt Rolle/Lesebereich/Auslöser/Takt/gültig bis unter deutschen Labels, keine englischen Schlüssel | `test_the_routine_question_names_everything_the_route_binds_to` (umgeschrieben) | grün |
| Leser nachgezogen | `test_kernel::test_the_two_document_routes_each_resolve_their_own_plan_on_the_command_line` (Label statt Enum), `test_hooks_v2::test_the_approval_question_names_what_gets_published` (deutsches Push-Formular) | grün |

### 5.2 AC-8 — die Auditor-Route (BUG-0266 / H184)

`routine_subject_manifest` als Zeilen-Builder; `request-approval routine <ROOT> --role --scope
--trigger --cadence --expires-in-days` (Pflicht für routine, sonst Verweigerung mit Satz);
`create-task --read-only` oder `--allowed-scope`, nie keines von beiden; **`approvals.presents`**:
eine hängende Art (routine, analysis) landet nicht mehr im `approval_ref` der Wurzel — gemessen
davor: nach der Routine-Prägung stand die Scope-Freigabe des Ziels nicht mehr vor, jeder Bauer
darunter wurde verweigert („obtain the scope approval") — für die leichte Form, in der der Auditor
neben einem laufenden Ziel aus der Session-Start-Erinnerung läuft, eine Falle, keine Randnotiz.
Zwei Tests, die das alte Verhalten festhielten, messen jetzt das neue
(`test_minting_a_routine_on_a_live_root_leaves_its_approval_ref_alone`, die Amendment-Probe mit
einem von Hand gesetzten Verweis). `_routine.py` nennt die Route im Hinweis (gespiegelt ×3; der ausgelieferte
Spiegel-sha steht einmal, in 3a bei Fix (4) — dieser Zwischenstand wurde davon überholt);
Auditor-Definitionen, -Skills und Verfassungen ×3 sagen nicht mehr „no
producer / not yet walkable", sondern die Zeile. Ende zu Ende auf der Kommandofläche:
`test_the_auditor_runs_on_the_routine_route_from_the_command_line_without_a_writable_scope`, und je
Kit im Pilot-Rig (5.5). Was bleibt: `analysis` hat weiterhin keinen Zeilen-Builder (die Texte sagen
es); Auslöser/Takt/Lesebereich werden gehasht, von keinem Gate gelesen (unverändert, gesagt).

### 5.3 AC-2 / AC-3 / AC-4 / AC-12 — die Texte

PM-/Lead-Skills ×3: ein identischer Block „THE LIGHT FORM" im DELEGATE/ROUTE-Schritt (ein Bauer mit
dem ganzen Ziel; zweiter nur mit `check-scopes`-Datensatz; `--rung/--effort` mit der
Drei-Zeilen-Regel des Nutzers wörtlich; **nie nach Stufen oder Teamgröße fragen**; die vier
Checkpoint-Zeilen; die ehrliche Grenze DEC-0092 (7)) und ein Block „VERIFICATION AT THE GOAL" im
GATE-Schritt (DEC-0088 (a)–(f)); der Satz „Nothing refuses an overlapping pair" ist in allen drei
Skills ersetzt; „Models & escalation" sagt „derived, never asked". Verfassungen ×3: Schritt 6/7 mit
Zeiger auf den Skill, §11/§7 „DERIVED, never asked", die Defaults-Zeile mit der Auftragsbitte.
Auditor-Skills ×3: Rückschau-Frage 5 (Bauerzahl gegen disjunkte Mengen, Wanduhr, Sprosse gegen
Ausgang, das Urteil als eigene Zeile mit Zahlen — identisch, `test_review_procedure` grün).
parallel-streams-Skills ×2 nennen den Datensatz.

| Leser | Test | rot auf |
|---|---|---|
| AC-2: keine Teamgrößen-Frage in Einstiegsdateien, Lead-Skills, Verfassungen (Vokabular beidseitig gemessen: die alten Sätze werden gelesen, der DEC-0048-Ausweg nicht) | `tools/test_hooks.py::test_no_entry_file_and_no_lead_text_asks_the_user_for_the_team_size` + `::test_the_team_size_reader_can_tell_a_question_from_the_escape` | dem Office-Skill-Satz „Preset confirm (recommend `core` first …)" (gemessen rot, dann ersetzt) |
| AC-4: kein Kit-Text ordnet einen Prüfer nach jeder Nacharbeit an; jeder Lead-Text trägt den Takt | `test_no_kit_text_still_orders_a_verifier_after_every_rework` + `test_the_cadence_reader_can_tell_an_order_from_its_negation` | dem Fixtursatz „After every rework the verifier runs the whole package again." |

### 5.4 AC-5 — der Einstieg

`user/claude/CLAUDE.md` und `user/codex/AGENTS.md` (Zwillinge): die Frage lautet »Mit
Langzeit-Gedächtnis für das Projekt (Projektakte, Entscheidungen, Beweise) — oder erstmal frei?«;
„mit" installiert sofort in der leichten Form mit dem KLEINSTEN Preset (das mit den wenigsten Rollen
in `presets.yaml`: `solo` in dev/research, `core` in office — gemessen vom Rig, siehe 5.5; office hat
kein `solo`, was der erste Rig-Lauf zeigte); das Produkt-Interview bleibt, kürzer; die
Teamgrößen-Frage samt Reversibilitätsklausel ist raus, der DEC-0048-Ausweg bleibt; kein Team-Abschnitt
im Masterplan mehr. Der TEAM-SIZE-Test von P4-6 ist durch den AC-2-Leser ersetzt. Die
deutsche Berichtsregel (FR-0048) steht unverändert oben in der Datei. Nicht gemessen: eine
Live-Einstiegssitzung, die die Frage stellt (die Grenze, die `test_hooks` für diesen Gegenstand
schon nennt).

### 5.5 DEC-0092 (6) — der Pilot-Rig

`tools/light_kit_pilot.py --out <außerhalb>`: je Kit ein vom Kit-eigenen Installer gebautes Projekt
(Store = Kopie von `team-kits/` unter eigenem HOME, **mit** `write_kit_state.py` — s. 5.7), drei
Bestellungen offensichtlich verschiedener Größe mit Bitten sonnet/opus/fable, Läufe: (Zeilen
unten sind die des Logs `_round-scratch/TSK-0135/pilots/light_kit_pilot.log.json`, Uhr vom Rig).
`test_the_pilot_rig_leases_three_orders_of_different_size_per_kit` fährt ihn als Prozess (≈30 s);
der Stempel ist seine Vorbedingung, also läuft er bei jedem Stempel, der die Leiter oder die
PM-Texte berührt — im Lieferlauf.

| Kit | kleinstes Preset installiert | PM-Codeschreibzugriff (registrierte Edit/Write-Kette) | 3 Leases (rung/effort) | 2. Bauer ohne Datensatz | Checkpoint | Auditor-Route |
|---|---|---|---|---|---|---|
| dev-team | solo (5 Rollen inkl. PM) | rc 2 | sonnet/high, opus/high, fable/xhigh | rc 1 | rc 0, 6 Zeilen | rc 0, `allowed_scope: []`, `approval_ref` der Wurzel bleibt APR-0001 |
| research-team | solo | rc 2 | sonnet/high, opus/high, fable/xhigh | rc 1 | rc 0 | rc 0 |
| office-team | core | rc 2 | sonnet/high, opus/high, **opus/high** (DEC-0078-Decke) | rc 1 | rc 0 | rc 0 |

Zwei Befunde des Rigs an sich selbst: (a) `gate_write_scope` ALLEIN verweigert den PM-Schreibzugriff
nicht (rc 0) — die Tür ist `guard_pm_scope` in der registrierten Kette; AC-1 ist mit der Kette
gemessen und so im Protokoll benannt; (b) office kennt kein `solo` (erster Lauf: „Invalid preset").

### 5.6 AC-6 — das Experiment (vorbereitet, der Grund gemessen; Lauf und Urteil sind Nutzerzeilen)

`project_memory/staging/TSK-0135/experiment/`: `brief.md` (die Aufgabe wörtlich für beide Arme:
Rechnungsübersicht als Offline-Web-Seite über `invoices.json`, fünf Punkte, Messgrößen, Fairness),
`invoices.json` (24 Einträge), `arm-a-fable-alone.md` (eine Headless-Sitzung, der Lead fährt sie),
`arm-b-kit.md` (der Aufbau in der leichten Form).

**Arm B ist aufgebaut**: `rig/arm_b.py prepare` fährt den Einstieg, wie die Einstiegsdatei ihn
vorschreibt — Kit-Store, `init_project_memory`, Masterplan, `project_config.yaml` (Name + Stack),
ein DRAFT `PR-0001` **durch den Kernel** erfasst, `generate-index`, `scaffold_team -Preset solo`:
alle fünf Schritte rc 0, installierte Rollen `backend-developer, project-auditor, project-manager,
quality-engineer, software-architect` (`experiment/prepare.log.json`).

**Der Grund, warum er nicht unbeaufsichtigt läuft, ist jetzt gemessen** (Zielrunde B1: er war die
einzige unvermessene Tatsachenbehauptung der Runde). Zwei `claude -p "weiter"`-Läufe im
vorbereiteten Projekt, Provider 2.1.267, Modell `haiku`, `--max-turns 30`, `AskUserQuestion`
ausdrücklich erlaubt; Lauf 2 zusätzlich mit `--dangerously-skip-permissions`:

| Lauf | Uhr | Züge | Werkzeugaufrufe | `AskUserQuestion` | Ende |
|---|---|---|---|---|---|
| 1 | 08:11:08–08:12:21 | 11 | 10 | **0** | `end_turn`, Frage in Prosa an den Nutzer |
| 2 | 08:14:02–08:14:33 | 5 | 4 | **0** | `end_turn`, „PR-0001 ist bereit für die Scope-Freigabe. Ich kann die Frage stellen, damit du sie freigeben kannst" |

Der PM **bleibt nicht am Tor stehen, er erreicht es nicht**: keine Freigabe-Anfrage, kein Lease,
kein Bauer-Spawn, `permission_denials: 0`, `--max-turns` weit unausgeschöpft. In `-p` ist die
Rückgabe an den Nutzer das Ende der Sitzung. Nebenmessung aus denselben Rohströmen: in beiden
Läufen starteten vier SessionStart-Haken und antworteten mit Code 0 — die Haken des Kits liefen;
verweigert hat der Provider nur die fünf `permissions.allow`-Einträge des nicht vertrauten
Arbeitsbereichs. Abgelegt als Eintrag `headless_pm_stop_point` in
`tools/provider_observations.json` (Datum, Provider-Version, Methode, Ort, und die zwei Dinge, die
sie nicht misst).

**Nicht gefahren wird der Arm selbst** — und das ist kein technischer Befund, sondern `DEC-0095`
(6): kein Experiment-Arm ohne das Wort des Nutzers, solange das Wochenbudget über der Hälfte steht.
Diese Entscheidung löst den Satz des Items ab („you PREPARE both arms **and run the kit arm**"),
der aus der Zeit vor ihr stammt. Was bleibt, sind zwei Nutzerzeilen (Abschnitt 8): der Lauf beider
Arme und das Qualitätsurteil. Die erste Messung der Form auf sich selbst ist dieses Ziel
(Abschnitt 7).

### 5.7 AC-11 — Rollout und Harvest

Harvest: `python tools/harvest_kit_gaps.py` gegen `portfoliomanaigement`, `synaipse`,
`synaipse-unified` (lesend): **0 Einträge, 0 zu triagieren** — zwei der drei Projekte laufen Kits
vor `report-gap` (2026.07.18-3), das dritte (2026.08.31-6) hat nichts gemeldet. Erster Eingang der
Gen-6-Rückschau: der Harvest ist leer, weil die Projekte den Stempel mit dem Gap-Log noch nicht
haben — die Route, die ihn bringt, ist die gemessene unten. Update-Route
(`rig/update_route.py`): Pilot aus dem Store @ `5048c18` (`git archive`, Repo unberührt) mit
`2026.09.06-1` installiert, Store durch den Gen-6-Baum ersetzt, dann SessionStart-Hook →
`request-approval kit_update` → Prägung → `update-kit` → `kit_version` danach. Ergebnis in Abschnitt 9
(Zeilen 04:4x); die ersten zwei Läufe fielen am fehlenden Rekorder in der Store-Kopie (5.5), ein
Befund über die Rigs, nicht über die Route.

## 6. Löcher (durch den Kernel erfasst) und benannte Reste

- **H193 / BUG-0277** (`capture BUG --hole`, 04:55): `scaffold_team` warnt nur, wenn die Staging kein
  `write_kit_state.py` trägt, und installiert mit unverifiziertem Bündel — die Datei ist zugleich
  Eingabe des Kit-Hashes, sodass dieselbe Staging bei jedem späteren Stempelvergleich verweigert
  wird (gemessen an zwei Rigs; Begrenzung: die Update-Route verweigert sie). Der Lead fährt
  `migrate-holes --reindex`.
- Benannt, kein Loch (keine Kette innerhalb einer Sitzung):
  1. Das Struktur-Gate greift nur, wo eine Leiter die Klasse `build` liefert, und nur unter EINEM
     Ziel — kitlos (dieses Repo) außerhalb (`test_a_kit_less_project_is_outside_the_second_builder_rule`).
  2. `scope-checks`-Datensätze über noch offene, langlebige Aufträge häufen sich je Lauf an, bis
     die Aufträge schließen (`_drop_records_about_closed_orders` räumt nur geschlossene).
  3. `analysis` hat weiterhin keinen Zeilen-Builder; Auslöser/Takt/Lesebereich der Routine werden
     gehasht, von keinem Gate gelesen (die Auditor-Texte sagen beides).
  4. Die Leser für AC-2 und AC-4 sind Vokabulare über Prosa mit beidseitigen Stolperdrähten — ein
     neuer Wortlaut derselben Frage kann an ihnen vorbei. Beide Docstrings sagen das jetzt auch:
     der von AC-4 sagte es schon, der von AC-2 behauptete bis zur Nacharbeit das Gegenteil („RED on
     any text", Zielrunde P3) und ist auf das gekürzt, was der Leser baut. Was die Nacharbeit
     geschlossen hat, war nicht die Vokabular-Natur, sondern zwei Löcher **in** den Vokabularen
     (B3: das Wort „derived"; B4: jedes „not" im Satz) — die Grenze selbst bleibt.
  5. Der SessionStart-Satz „KIT UPDATE AVAILABLE" auf dem Update-Route-Piloten wurde vom Rig nicht
     eingefangen (Extraktion), nur die Route selbst ist gemessen.
  6. Der Kit-Arm des Experiments ist aufgebaut und **nicht gefahren** — seit der Nacharbeit mit
     gemessener statt behaupteter Begründung (5.6) und mit `DEC-0095` (6) als dem, was ihn
     zurückhält; der Lauf und das Qualitätsurteil sind Nutzerzeilen.
  7. `harness-lead.md`/`-implementer.md`/`-verifier.md` tragen den DEC-0088-Takt für dieses Repo nicht;
     die ACs verlangen ihn für die Kit-Texte, und DEC-0094s Zeilen für den Lead sind seine.
  8. **Bewusst offen gelassen, Nacharbeit (P6 der Zielrunde):** das Ablaufdatum in der deutschen
     Freigabefrage bleibt maschinell (`2026-09-25T05:06:25Z`) statt lesbar (`25.09.2026, 05:06 UTC`).
     Es liegt in `kernel/approvals.py`, also in einem Kit-Datei-Hash: die Änderung kostet einen neuen
     Stempel und zieht die Suiten nach, die die Frage **zeichenweise** vergleichen (`gate_approval`),
     und die Zielrunde stuft den Befund als „niedrig" ein. Unter `DEC-0095` (6) ist das der falsche
     Preis für eine Nacharbeitsrunde; die Zeile gehört als `FR` in den Eingang, nicht in diese Runde.
  9. **Die AC-6-Messung misst zwei Dinge nicht**, und sie sagt es an ihrem eigenen Ort
     (`headless_pm_stop_point.not_measured`): ob ein **stärkeres Modell** den Bauer losschickt, bevor
     es abgibt (beide Läufe sind `haiku`), und ob eine **interaktive** Sitzung die drei Prägungen
     wirklich durchläuft — das ist genau der Lauf, den der Nutzer noch schuldet. Nicht angefasst
     wurde dafür die Provider-Konfiguration des Nutzers (`~/.claude.json`): der Arbeitsbereich des
     Piloten bleibt „nicht vertraut", weshalb der Provider seine fünf `permissions.allow`-Einträge
     ignoriert — die Haken selbst liefen (vier SessionStart-Prozesse, Code 0).

## 7. (g) — die Form auf sich selbst, gegen die Ströme der Generation 5 (AC-10)

Quellen für Gen 5: `project_memory/staging/generation-5-streams.md` (Zeilen 118, 175–176, 206, 293),
DEC-0094 context. Meine Zahlen: der Restzähler des Budgets (15 000 000 beim Start jeder Sitzung),
die Uhr des Rundenlogs, die Zwischenchecks.

| | Form | Tokens | Prüferrunden | Wanduhr | Tool-Aufrufe |
|---|---|---|---|---|---|
| G5-1 stock (TSK-0131) | Strom, Opus (nach Fable-Vorgänger) | ~896 k (Rework 2 kumuliert) | 4 (FAIL/FAIL/FAIL-ohne-Blocker/…) | ~8 h 10 inkl. Warten (Rework 2) | 332 |
| G5-2 ladders (TSK-0130) | Strom, Opus | ~649 k | 2 (+1 nach den Routinen) | ~10 h 56 inkl. Suiten (Rework 1) | 442 |
| G5-3 office (TSK-0132) | Strom, Opus | ~630 k | 3 (FAIL/FAIL/PASS) | 5:46 gearbeitet über 13:23 Spanne | 365 (Rework 2) |
| G5 merge (TSK-0133) | Fable | ~770 k über zwei Sitzungen | 1 voll + 1 kurz | — | — |
| **G6 das leichte Kit (TSK-0135)** | **ein Bauer, Fable high, das ganze Ziel (12 ACs)** | **~937 k bis zur Lieferung** (15 000 000 → 14 063 477; davon ~886 k bis zum Start des ersten Volllaufs) + **~210 k** diese Nacharbeit (Opus high, eigener Restzähler 15,00 M → 14,79 M beim Schreiben dieser Zeile); die Zielrunde (Opus-Prüfer) und die abgebrochene erste Nacharbeit sind **nicht gezählt** | **1 Zwischencheck (Opus, 03:31–03:45, 14 min) + 1 Zielrunde (Opus, FAIL: 8 von 12 PASS, Bericht 07:54) + 1 Nacharbeit (Opus, ab 07:56)** | **Lieferung 02:34 → 06:47 = 4 h 13 min** (davon 2 h 24 gebaut und gemessen, ~1 h 33 Warten auf zwei Volläufe (39:31 + 39:55) und die Gate-Suite (12:37), der Rest die acht Lieferlauf-Befunde); **mit Zielrunde und Nacharbeit 02:34 → 08:42 = 6 h 08 min** | nicht gezählt |

Was die Zeile sagt, **je Behauptung gegen genau eine Bezugsgröße** (die Zielrunde hatte hier eine
Zusammenfassung gefunden, die ihrer eigenen Tabelle widersprach — B2):

- **Tokens gegen einen einzelnen Strom: G6 ist teurer, nicht billiger.** 937 k gegen 896 k, 649 k,
  630 k — also rund 1,05× des teuersten und rund 1,5× des billigsten Gen-5-Stroms.
- **Tokens gegen die ganze Generation:** 937 k gegen ~2,95 M (896 + 649 + 630 + 770 k Merge) —
  rund **ein Drittel**. Das ist der Vergleich, der zur Größe des Ziels passt: zwölf Kriterien,
  Kernel + Gates + Texte + Einstieg + zwei Routen + Rig + Rollout, also die Fläche dreier Ströme
  plus deren Merge-Nähte.
- **Wanduhr gegen einen einzelnen Strom (Spanne gegen Spanne):** 4 h 13 (253 min) gegen 8 h 10
  (490), 10 h 56 (656) und 13 h 23 (803) — 0,52 / 0,39 / 0,31, also **rund ein Drittel bis gut die
  Hälfte** eines Stroms.
- **Wanduhr gegen die Summe der drei Spannen** (1949 min): rund **ein Achtel**.
- **Mit Prüfung gerechnet** (Zielrunde + Nacharbeit, 02:34 → 08:42 = 368 min): 0,75 / 0,56 / 0,46
  eines Stroms und rund **ein Fünftel** ihrer Summe — die ehrlichere Zahl, weil die Gen-5-Spannen
  ihre Prüferrunden enthalten.
- **Runden:** 1 Zwischencheck + 1 Zielrunde + 1 Nacharbeit gegen 2–4 Prüferrunden je Gen-5-Strom
  plus 1 volle + 1 kurze im Merge.

Was nicht drinsteht: die Tokens der Zielrunde und der abgebrochenen ersten Nacharbeit (nicht
gezählt), die Nähte, die ein Merge gefunden hätte (hier gibt es keinen — ein Baum, ein Schreiber),
und ob die Qualität hält — das messen die Zielrunde (8 von 12 beim ersten Anlauf) und der Nutzer.
Die Zahl ist die erste Messung der Form auf sich selbst, kein Urteil über sie.

## 8. Zeilen für den Lead und für den Nutzer

**Zwei EVD-Zeilen** (zustandsrelative Verweise innerhalb des Repos, kein Digest):

    PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory evidence --kind test --result pass --related PR-0011 --related TSK-0135 --summary "TSK-0135 delivery run after stamp 2026.09.11-4: tools/ 4882 passed / 14 skipped / 0 failed in 2395 s (run 2; run 1 on -3 had 8 reds, each closed red-first), .claude/hooks/test_gates.py 548 passed in 757 s, both with the delivery prefix; ruff and validate green; 41 red-first rows red (red_first-20260911-045313.log.json); pilot rig green per kit (light_kit_pilot.log.json)" --artifact-ref staging/TSK-0135/protocol.md --artifact-ref staging/TSK-0135/full-tools-run-2.log --artifact-ref staging/TSK-0135/full-gates-run-1.log --run-scope full --run-command "DELIVERY_RUN=TSK-0135 python -B -m pytest tools/ -q -p no:cacheprovider"
    PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory evidence --kind review --result <pass|fail> --related PR-0011 --related TSK-0135 --summary "<the goal-round verdict per AC>" --artifact-ref staging/TSK-0135/verify-goal.md

**Dritte EVD-Zeile für die Nacharbeit** (dieselbe Form; no kit file changed, so the stamp stays
2026.09.11-4):

    PYTHONPATH=team-kits python -B -m kernel.cli --root project_memory evidence --kind test --result pass --related PR-0011 --related TSK-0135 --summary "TSK-0135 rework after the goal round (B1-B5, P1-P5, P7): 12 red-first rows R1-R12 all rc 1 with the arbiter's failure line (red_first_rework-20260911-082057.log.json 08:21:18-08:25:30 and -084034 08:40:36-08:40:44, own copy); AC-6 arm B prepared (5 steps rc 0) and the asserted reason MEASURED in two claude -p runs, zero AskUserQuestion, filed as headless_pm_stop_point in tools/provider_observations.json; reading suites green after the changes: test_light_kit 26, test_repo_hygiene+test_shortening_net 68, test_role_contracts+test_context_budget 72, test_hooks -k entry/team_size/first_contact/deadline 26, test_hooks_v2 -k provider/channel/event 12; ruff and validate green; bump_kit_version unchanged (2026.09.11-4) x3" --artifact-ref staging/TSK-0135/protocol.md --artifact-ref staging/TSK-0135/red_first_rework-20260911-082057.log.json --artifact-ref staging/TSK-0135/red_first_rework-20260911-084034.log.json --artifact-ref staging/TSK-0135/experiment/probe-20260911-081402.summary.json --run-scope selection --run-command "python -B -m pytest tools/test_light_kit.py -q -p no:cacheprovider"

(Die Log-Dateien liegen LF-geschrieben in `staging/TSK-0135/`, s. 3a; DEC-0094 (9).) Der Reindex
der Löcher (H193) ist gefahren; nach der Zielrunde bleibt für den Lead: EVD, Transitionen, ein
etwaiger weiterer Reindex nach eigenen Captures.

**Für den Nutzer** (DEC-0093 (4), ein Bündel bei seiner Rückkehr):
1. Plan-/Scope-Prägung von PR-0011 (die Frage stellt der Kernel; sie ist jetzt deutsch).
2. **Das Experiment (FR-0089 / AC-6) wartet auf ein Wort des Nutzers, nicht auf Technik.** Beide Arme
   sind vorbereitet, Arm B ist aufgebaut, und dass eine unbeaufsichtigte Sitzung ihn nicht fahren
   kann, ist gemessen (5.6). Gefahren wird er trotzdem nicht: `DEC-0095` (6) verbietet einen
   Experiment-Arm, solange das Wochenbudget über der Hälfte steht. Sagt der Nutzer ja, fährt der
   Lead Arm A nach `experiment/arm-a-fable-alone.md` und Arm B interaktiv nach `arm-b-kit.md` (drei
   Klicks an den Toren), dann öffnet der Nutzer zwei `index.html` und benotet. Die Standard-Stufe
   des Bauers ist **nicht mehr die Frage** — `DEC-0095` (1) setzt sie aus Kosten auf Opus; das
   Experiment misst seit `DEC-0095` (7) das Kit auf Opus gegen Fable allein.
3. Die vier lokalen Routinen der Watcher (TSK-0134, AC-9): zwei Desktop-Aufgaben, zwei Codex-Automations.
4. Push — kein Push ohne sein Wort.
5. Die Abnahme-Prägungen PR-0004..0010 und später PR-0011.
6. Der Rollout: die drei installierten Projekte (portfoliomanaigement 2026.08.31-6, synaipse und
   synaipse-unified 2026.07.18-3) bekommen den Stempel beim nächsten Sitzungsstart über `update-kit` —
   die Route ist gemessen (5.7); die Session-Start-Frage stellt der jeweilige PM, der Nutzer klickt.

## 9. Rohprotokoll (Uhr vom Skript gelesen, `rig/log.py`; identisch mit `protocol-log.md` neben dieser Datei)

Rundenbeginn: Spawn 02:34 (Rundenlog des Leads); die erste Zeile unten ist die erste, die das Gate durchließ (zwei frühere Versuche verweigert: relativer Pfad nach `cd`, dann ein `*` im Text). 21 Zeilen.

- 2026-09-11 02:43:34  MEASURED: the three installed projects (portfoliomanaigement dev-team 2026.08.31-6, synaipse + synaipse-unified dev-team 2026.07.18-3) carry NO task with rung/effort -- giving the TSK fields the DEC-0091 meaning (the PM's ask) rebinds nothing stored. PLAN written next; build order: kernel contract (backlog_types + dispatch + cli + scopes record + report distribution + brief schema) -> gate rule -> checkpoint in gate_dispatch -> reading suites -> HALF.
- 2026-09-11 03:00:49  PHASE 1 BUILT: backlog_types TSK_RUNG_FIELD/TSK_EFFORT_FIELD (OPTIONAL_FIELDS + TSK_PLAN_FIELDS); dispatch: order_tiers, rung_vocabulary/_reference_rungs (pass-through row), _assert_the_order_tiers_are_placeable in create_task, EFFORT_LEVELS, BUILD_CLASS, LEASE_RUNG/EFFORT/CLASS_FIELD, MEASURED_DISJOINT_KEY, ladder_for_order max() with floor/start/order, _valid_ladder build class + effort vocabulary, running_leases/concurrent_builders/_assert_a_second_builder_was_measured_locked, reflection_checkpoint + CHECKPOINT_QUESTION; scopes: asks per order, order_digest, write_record/records/covering_record, goal_partition; layout: scope-checks subtree; report: lease_distribution + brief field + lease rows; schema session_brief lease_distribution; cli create-task --rung/--effort; gate_dispatch _mirror_the_builder_start (mirrored x3, sha 51667967173de368). Suites: test_ladder 35 passed 16.5s, test_report -k brief 5 passed, test_parallel_scopes+streams 45 passed 23s, NEW tools/test_light_kit.py 14 passed 8.8s.
- 2026-09-11 03:12:33  RED-FIRST RIG phase 1: 23 rows M1..M18 all rc 1 for the named reason (rig/red_first.log.json, 03:02:11-03:03:19; M11b re-run 03:04:35 shows rc 0 held and the fallback line 'the checkpoint could not be derived (RuntimeError: boom); the spawn stands'). READING SUITES so far: kernel 131, state 61, model_ladder 12, e2e 20, review_procedure 27, role_contracts 30, staging_cli 98, schemas+backlog_types 80 all passed; board 1 red (scopes.write_record not in the board's writer exemption map -> entry added with reason); approvals_dispatch 2 red: (1) the status-write reader could not read the alias RUNG_KEY = TSK_RUNG_FIELD -> reader extended one hop over sibling imports with a both-ends tripwire; (2) architect-step test leased a second builder under one goal -> it now runs check-scopes first, as a PM must (DEC-0092 (2)); reference_skills 2 + research_chain 10 errors from the SCAFFOLD refusing (tail read next -- the unbumped stamp is the suspect, house rule 7).
- 2026-09-11 03:23:47  STAMP 2026.09.11-1 (intermediate, house rule 7) at 03:13; after it: approvals_dispatch 197 passed 82s, board 77 passed, reference_skills 18 passed 51s, research_chain 10 passed 41s, migrate -k brief/subtree 1 passed, hooks_v2 -k dispatch/spawn/chain/lease 62 passed 32s, hooks -k gate_dispatch selection 10 passed, shortening_net 36, context_budget 42, kitupdate 86 passed + 1 skipped 240s. protocol.md written (sections 0-4, 9 pending). Next: wider test_hooks selection, validate, then the HALF report to the lead.
- 2026-09-11 03:25:03  HALF REPORTED to the lead: kernel contract + structural gate + checkpoint + distribution line built and measured; test_hooks_v2 -k preamble 10 passed; validate + ruff green after the intermediate stamp 2026.09.11-1. Waiting for the lead's word (Opus mid-goal check) before phase 2 (rig, retrospective rule, texts, entry file, approval question, auditor route, experiment arms, rollout + harvest).
- 2026-09-11 03:53:53  MID-GOAL CHECK read (verify-half.md, Opus 03:31-03:45): CONTINUE with B1 (mirror not inside try -> rc 2 after spent claim), B2 (effort exception lifted by an ask), B3 (covering_record reads the newest DISJOINT record, not the newest over the pair), B4 (kit-less rungs high->low), B5 (property tripwire cannot go red), B6 (line (a) unbounded), P1-P8, plus AC-12 free-text reader and scope-checks growth. Phase 2 starts with these, each with a rig row.
- 2026-09-11 03:57:13  P3 MEASURED LIVE (claude 2.1.258, scratch project probe-pre-context, one PreToolUse(Bash) hook, exit 0): the model's answer was 'hello' + 'PRE-CONTEXT-MARKER-9b7d' -- hookSpecificOutput.additionalContext on PreToolUse REACHES THE MODEL; the systemMessage marker (SYSMSG-MARKER-4c2e) was not repeated by the model; hook log 03:55:27; cost 1 turn, 2 API iterations. B1/B2/B3/B4/B6/P1/P4/P8 code edits applied; model_tiers.yaml gained the ordered rungs line (B4).
- 2026-09-11 04:08:01  MID-GOAL FINDINGS CLOSED: B1 (mirror guard, new process test with a raising record_note), B2 (effort exception = floor and ceiling, filing-pair test + ask case), B3 (newest record naming the pair; record names carry microseconds), B4 (model_tiers.yaml rungs line low->high), B5 (synthetic tables), B6 (line (a) bounded), P1/P2/P4/P5/P6/P8 wording, P7 six-rung test, AC-12 surface reader, scope-checks prune. Suites: light_kit 20 + ladder + schemas + report = 210 passed 55s. Rig: phase-1 rows all red again (04:04-04:05), V-rows all red (04:05:53-04:06:29) except the dropped non-defect variant. Mirror x3 sha 8732487ea375abd8.
- 2026-09-11 04:26:52  AC-7 + AC-8 BUILT: approvals KIND_LABELS (two-sided tripwire) + MANIFEST_LABELS + item_title in the request + build_question German sentence (hash/path moved into the approving option's description, marker stays) + push form German; routine_subject_manifest as line builder, cli request-approval routine ROOT --role/--scope/--trigger/--cadence --expires-in-days, create-task --read-only (or --allowed-scope, never neither); approvals.presents: a hanging kind (routine, analysis) no longer displaces the root's approval_ref -- measured trap for the light form (builders stopped after the audit's mint); _routine.py notice names the route (mirrored x3, sha ebfb2fcadea2855a); auditor agents/skills/constitutions x3 updated. Tests: light_kit 23 passed, approvals_dispatch 197 passed 85s (two tests rewritten: leaves_its_approval_ref_alone; forged-ref shape), hooks_v2 -k approval 116 passed after two reader fixes.
- 2026-09-11 04:38:08  TEXTS + ENTRY BUILT: user/claude/CLAUDE.md + user/codex/AGENTS.md carry the new first-contact question (DEC-0087 (4)), no team-size question, solo default, shorter interview; PM/lead skills x3 carry the light-form block (one builder, check-scopes record, --rung/--effort with the user's three-line rule, never ask tiers/team size, the four-line checkpoint, DEC-0092 (7) honest limit) and the cadence block (DEC-0088 a-f); constitutions x3 step 6/7 + presets paragraphs; auditor skills x3 retrospective question 5 (habit verdict with numbers); parallel-streams x2 name the record. New readers: test_hooks team-size reader (two-ended) red on the office skill's Preset confirm until fixed; test_light_kit cadence reader (negation-aware, two-ended). Intermediate stamp renewed for the scaffold-based suites and the pilot rig.
- 2026-09-11 04:42:58  PILOT RIG tools/light_kit_pilot.py measured 04:38 and again after two fixes: dev/research lease sonnet/opus/fable at high/high/xhigh as asked; office bookkeeper capped to sonnet/opus/opus at high (DEC-0078 ceiling); second builder without record rc 1; checkpoint rc 0 with the four lines; auditor routine route rc 0 from the entry point, allowed_scope empty and the root's approval_ref still the scope APR; lead code write rc 2 through the REGISTERED Edit-Write chain (guard_pm_scope then gate_write_scope -- gate_write_scope alone gave rc 0 in the first run); smallest preset derived (solo/solo/core) -- office has no solo, the entry files now say 'fewest roles'. Whole rig 18-20 s per run; pytest wrapper 1 passed 30.6 s. HARVEST (AC-11) ran read-only against portfoliomanaigement, synaipse, synaipse-unified: 0 entries, 0 to triage.
- 2026-09-11 04:46:02  UPDATE ROUTE (AC-11) first two runs refused the NEW store as 'does not hash to its own VERSION' (1e2664f5005e vs cf05ce7e9cb9): the rig had removed write_kit_state.py from the store copy (the TSK-0130 rig's habit) and that file IS a kit-hash input (rig/hash_compare.py: repo cf05ce7e9cb9 = fresh copy with recorder; copy without it 1e2664f5005e). Side finding: scaffold_team.ps1 only WARNS when the recorder is missing and records no bundle trust, so the earlier pilot runs scaffolded with hook_trust unverified. Both rigs now keep the recorder; re-running.
- 2026-09-11 04:51:32  UPDATE ROUTE measured 04:46:48-57 with the recorder kept: pilot from the 5048c18 store at 2026.09.06-1, store replaced by this tree (2026.09.11-2), request-approval kit_update rc 0 (question still the OLD kernel's -- English keys -- because the pilot runs the installed kernel until the update lands), mint through the hook, update-kit rc 0 -> kit_version 2026.09.11-2, HANDOVER_PENDING set; the SessionStart 'KIT UPDATE AVAILABLE' sentence was not captured by the rig's extraction (not measured). RIG ROWS P3: AC7a/b/c/d, AC8a/b/c, AC4 red for the named reason; AC2 stayed GREEN -> the team-size reader judged the negation per block, now per sentence (mixed-block fixture added). validate: lead packages 1.6-1.7 KB over the recorded ceiling -> constitution blocks trimmed, record to follow with a note.
- 2026-09-11 04:57:11  FINAL RIG RUN 04:52-04:55: all 41 rows rc 1 (M1-M18, V-B1..V-B6/V-P7/V-PRUNE/V-AC12, P3-AC7a-d, P3-AC8a-c, P3-AC2, P3-AC4). Lead package sizes recorded with note (+1303/+1224/+1401 B after trimming the constitution blocks). STAMP 2026.09.11-3 (dev/office/research). HOLE captured through the kernel: BUG-0277 = H193 (scaffold warns instead of refusing without the recorder). FULL DELIVERY RUN started 04:55:5x in the background: DELIVERY_RUN=TSK-0135 python -B -m pytest tools/ -q, timeout 6840 s (2280 s quiet x 3), log full-tools-run-1.log. No pytest until it ends.
- 2026-09-11 05:38:23  FULL DELIVERY RUN 1 (DELIVERY_RUN=TSK-0135, after stamp 2026.09.11-3): 04:55:5x -> 05:35:29, 8 failed / 4874 passed / 14 skipped in 2371.94 s (39:31) -- quiet host, matches the 38 min baseline; the derived 6840 s limit was 2.9x the need. Reds: test_disposition code citation, test_hooks entry-gate hooks + kit root item, test_parallel_streams audited-role cadence text, test_repo_hygiene test pointer + hole index, test_report non-dispatching approval, test_shortening_net pinned section. Reading each, fixing red-first, then reading suites, one more stamp, one more full run.
- 2026-09-11 05:45:57  EIGHT REDS OF FULL RUN 1 CLOSED: (1) disposition doc cited the renamed test -> the three historical lines now cite the new name and say it measures the opposite since gen 6; (2) entry-file preset blocks named office-team beside gate_memory_complete -> 'the office kit' wording, no kit key; (3) research/office texts named PR-0011 -> 'generation 6 (BUG-0266)'; (4) 'weekly' in the constitutions' route line -> '--cadence <how often>' (constitutions, auditor skills, hook notice, mirrored sha 1e6b941e1f45ab2a); (5) five kernel comments cited test_ladder.py -> test_light_kit.py; (6) migrate-holes --reindex: 183 holes, H193 indexed; (7) test_report non-dispatching-approval test writes the displaced ref by hand and asserts the mint leaves it alone; (8) constitution pins re-recorded with note (14 sections). Lead package sizes re-recorded (+4 B). Reader suites: hooks selection 27, parallel_streams+repo_hygiene+shortening_net+routine_feed 128, report+review+light_kit+role_contracts+context_budget+disposition 259 -> all green after the record. Stamp 2026.09.11-4.
- 2026-09-11 06:26:55  FULL DELIVERY RUN 2 (DELIVERY_RUN=TSK-0135, stamp 2026.09.11-4): 05:46 -> 06:26:07, 4882 passed / 14 skipped / 0 failed in 2395.10 s (39:55), rc 0, log full-tools-run-2.log. GATES SUITE started 06:26 in the background with the same prefix, limit 4140 s (1380 s x 3).
- 2026-09-11 06:46:40  GATES SUITE (DELIVERY_RUN=TSK-0135, stamp 2026.09.11-4): 06:26 -> 06:39:30, 548 passed in 757.25 s (12:37), rc 0, log full-gates-run-1.log. DELIVERY COMPLETE: stamp 2026.09.11-4, tools/ 4882 passed / 14 skipped / 0 failed, gates 548 passed, ruff and validate green, 41 red-first rows red, pilot rig green per kit, update route measured, harvest run. Tokens used 15000000 -> ~14063000 (about 937 k); wall 02:34 -> 06:47 of which about 1 h 33 waiting on the two full runs and the gates run.
- 2026-09-11 08:05:17  REWORK STARTED after goal round 8 of 12 PASS: B3 regex derived dropped plus docstring, B4 negated-order reader plus Pruefer, B5 first-contact reader written and green - 3 passed hooks first_contact or team_size, 2 passed light_kit cadence. P7 pilot cadence values German. Now arm-b prepare plus headless probe for AC-6, per lead under DEC-0095 6 no arm run.
- 2026-09-11 08:36:45  REWORK MEASURED: AC-6 arm B prepared (5 steps rc 0) and the asserted reason MEASURED -- two claude -p runs (2.1.267, haiku) 08:11:08-08:12:21 and 08:14:02-08:14:33, ZERO AskUserQuestion, end_turn, hand-back in prose; filed as headless_pm_stop_point in tools/provider_observations.json; arm-b-kit.md and protocol 0a/5.6 rewritten to prepared + reason measured + run and verdict = user lines (DEC-0095 (6) supersedes the item's run the kit arm). RED-FIRST rework rig: 10 rows R1-R10 all rc 1, 08:21:18-08:25:30, own copy rework/ (log red_first_rework-20260911-082057.log.json staged LF). P1: the 41-row log red_first-20260911-045313.log.json staged and named in 3a. Suites after the changes: light_kit 26, repo_hygiene+shortening_net 68, role_contracts+context_budget 72, hooks -k entry/team_size/first_contact/deadline 26, hooks_v2 -k provider/channel/event 12 -- all passed; ruff and validate green; bump_kit_version: unchanged (2026.09.11-4) x3, no kit file touched.
- 2026-09-11 08:42:33  REWORK CLOSED: three dead alternatives dropped from the AC-2 negation (never asked / NEVER ask are already matched by never ask under IGNORECASE) and the survivor MEASURED as the carrier of both shipped wordings -- rows R11/R12 rc 1 (red_first_rework-20260911-084034.log.json). Protocol 0a/3a/5.6/6/7/8 final: (g) rewritten against its own table with ONE reference base per claim (937 k is MORE than each gen-5 stream and about a third of the generation; 253 min is a third to a half of ONE stream span and about an eighth of their sum; with the goal round and this rework 368 min (02:34 -> 08:42) = about a fifth), Stand 04:58 dropped, the stale _routine sha replaced by a pointer to 3a in BOTH places, P6 named as deliberately NOT closed. After the last edit: hooks -k team_size/first_contact 3 passed, repo_hygiene 32 passed, ruff green.
