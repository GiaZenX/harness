# TSK-0151 -- Prüfrunde 1 (harness-verifier)

Beginn 2026-09-25T19:16, Ende ca. 19:40 (Uhr gelesen). Arbeitskopie:
`C:\Offline Repos\v2-testbed\_round-scratch\TSK-0151\verify\tree` (shutil.copytree, bytegenau, ohne .git).
Basis-Varianten `basetree` (Kernel, Tabelle, vier Leitern auf 8677bd2), `basetree_tbl` (nur die Tabelle
auf 8677bd2), `basetree_rr` (nur `radar_routine.py` auf 8677bd2), `patched`/`patched1` (Nutzer-Patch
angewendet). Rig-Skripte (`copy_tree.py`, `make_base.py`, `mutate.py`, `xcheck_tokens.py`) verweigern jedes
Arbeitsverzeichnis außer ihrem eigenen und lesen/schreiben binär. Proben liegen nur in der Kopie
(`tools/test_zz_verify_probe.py`, `tools/test_zz_verify_lease.py`). Kein Log und kein Transkript ganz
gelesen; das Protokoll nach Abschnitten (0-7 und "Rework F1").

## Befunde

### V1 -- Die Codex-Spitze fehlt auf dem Pfad, der LÄUFT: der Dispatch-Kopf rechnet nur für Claude (BLOCKIEREND)
- `team-kits/kernel/dispatch.py:759` (`create_lease`) und `:3740` (Nachrechnung beim Spawn) rufen
  `ladder_for_order(...)` ohne Provider auf, also immer für den Referenz-Provider (claude).
- Gemessen (`test_zz_verify_lease.py`, dev-team, Ziel `large`, Rolle software-architect):
  - 8677bd2: `software-architect lease rung=fable ... top fable`
  - jetzt:   `software-architect lease rung=opus ... top opus (the declaration says fable; claude caps it, DEC-0114 (4))`
  Der Lease hat keinen Provider -- auf einem Codex-Projekt steht derselbe Kopf da.
- Laut H173 (`BUG-0255`) steht die Sprosse auf Codex NUR in Lease und Kopf. Der einzige Codex-Träger der
  Sprosse nennt also seit dieser Runde opus statt fable. `gpt-6-astra` erreicht nur noch, wer
  `ladder <TSK> --provider codex` von Hand fährt; die Verfassungen schicken den Lead zu
  `python scripts/harness.py ladder <TSK-ID>` OHNE `--provider` (dev `AGENTS.md:410`, research `:381`,
  office `:457`) -- das liefert auf Codex die Claude-Antwort. Kein Kit-Text nennt `--provider`
  (grep über team-kits: nur `kernel/cli.py:908`).
- Diese Texte behaupten mehr, als gebaut ist: dev/research `skills/project-manager/SKILL.md` ("on Codex both
  still reach the top"), `README.md` Models-Punkt ("on Codex both still reach `gpt-6-astra`"),
  `dev-team/ladder.yaml` Klassen-Kommentar ("on Codex it is this file's `fable`, reached by the architecture
  step and by the escalation"), `team-kits/model_tiers.yaml` Kopf des `provider_top`-Blocks.
- Die Lücke steht nur im Protokoll ("Named, not closed"), nicht in der Löcherliste (der Diff von
  `docs/POST_V2_WISHLIST.md` enthält nur die Statusänderungen des Leads).
- Das ist genau F1, nur eine Ebene tiefer: F1 verlangte "on Codex the architecture class and the escalation
  still reach the top rung exactly as before 8677bd2". Auf der Nebenbefehl-Antwort stimmt das, auf dem Kopf nicht.
- Kleinster Fix, eins von beidem: (a) `dispatch --provider` (der Lease trägt den Provider, das Spawn-Gate
  rechnet mit ihm nach), oder (b) die Lücke als Loch eintragen (Mechanismus, gemessene Kette, Begrenzung:
  auf Codex wird am Spawn ohnehin nichts gehalten, H173), die vier Textstellen auf das Gebaute
  zurückschneiden und in die Ladder-Absätze der Verfassungen schreiben: "auf Codex: `harness.py ladder
  <TSK-ID> --provider codex`".

### V2 -- Eine Frage oder ein Pin oberhalb der Kappe ergibt eine negative Sprossenzahl, und die hebt den Effort schon bei FAIL 0 (nicht blockierend; in die Löcherliste oder Folge-Item)
- `team-kits/kernel/dispatch.py:3550`: `granted_rungs = rungs.index(chosen) - rungs.index(start)` wird
  negativ, wenn `start` über dem gekappten `top` liegt; `:3601` `on_this_rung = failed_runs -
  granted_rungs * per_rung` zählt dann drei Fehlschläge, die es nicht gab.
- Gemessen (`test_zz_verify_probe.py`, Claude): `dev-team backend-developer ask fable prov=None: 0:opus/xhigh`,
  Eskalationszeile `FAIL 0: rung +-1, effort +1`; ohne Frage `0:opus/high`. Dasselbe bei `pin fable`, beim
  research methodologist und beim office office-developer (`0:opus/high` statt `medium`).
- Die Zeile selbst ist im Diff unverändert: auf 8677bd2 war der Mechanismus nur im office-Kit erreichbar
  (top opus). Die Kappe macht ihn für jede `rung: fable`-Frage und jeden fable-Pin in dev/research auf
  Claude erreichbar. Die Claude-Hälfte von `test_no_shipped_ladder_answer_reaches_the_top_rung_bug_0306`
  sieht das nicht, weil sie nur Monotonie und die Decke am Ende prüft.
- Fix: `start` auf `top` klemmen (oder `max(..., 0)`); dazu ein Test: FAIL 0 mit einer Frage über der
  Spitze hat den Effort ohne Frage und `rung +0`.

### V3 -- Der Preis-Leser liest weniger, als der Docstring verspricht (BLOCKIEREND nach Regel 3/6, kleiner Fix)
- `tools/test_model_ladder.py:90-94` (`PRICE_RX`) gegen den Docstring `:108` "carries no price anywhere".
- Mutationen (eine Kommentarzeile vor `# NO PRICES IN THIS FILE`), Testknoten
  `test_the_tier_table_carries_no_price_and_says_what_each_rung_is_for_bug_0306`:
  Kontrolle `$15/$75` RED; `15 $ in / 75 $ out` GREEN; `15€/75€` GREEN; `15 dollars in and 75 dollars out`
  GREEN; `0.002 per 1K tokens` GREEN.
- Die Datei selbst ist heute sauber (grep nach `$ € dollar cent 1K price`: nur die Prosa "NO PRICES" und
  "price promotion").
- Fix: Währungszeichen auf beiden Seiten des Betrags, Währungswörter, `per 1K|1M`, oder den Docstring auf
  die gelesenen Schreibweisen einengen.

### V4 -- Der Leser für "no X row" erkennt die volle Modell-ID nicht (BLOCKIEREND nach Regel 6, kleiner Fix)
- `tools/test_model_ladder.py:145-151`: `name in model.split("-")` -- `gpt-6-luna` ist kein Element von
  `["gpt","6","luna"]`.
- Mutation im Kopf: `there is no luna row` RED (Kontrolle); `there is no gpt-6-luna row` GREEN;
  `there is no row for luna` GREEN. Der Docstring sagt "a sentence that denies a row by a model name".
- Fix: gegen die ganze ID UND ihre Teile vergleichen, oder den Docstring auf die gelesene Form einengen.

### V5 -- Der Nutzer-Patch ist an Stelle 2 nicht idempotent, obwohl sein Docstring das zusagt (BLOCKIEREND, einzeiliger Fix)
- `project_memory/staging/TSK-0151/apply_user_patch.py:102-105`: `n_before == 1` wird VOR "AFTER ist
  schon da" geprüft. Der BEFORE-Text von Stelle 2 ist ein Präfix ihres AFTER-Textes, bleibt also nach
  dem Anwenden genau einmal stehen.
- Gemessen in `patched`: `--check` rc 0 mit 6 Stellen; Anwenden rc 0 mit "DONE -- 6"; zweites `--check`:
  "already done" für 1/3/4/5/6, aber `would change 2 order cost lines`; zweiter Lauf: "DONE -- 1 site(s)
  changed"; danach `grep -c "Three cost lines every order carries" harness-lead.md` = **2**.
- Der Docstring (`:15-16`) verspricht: "or its AFTER text is already there -- then the site counts as done".
  Ein Nutzer, der nach der gemeldeten Overlay-Panne (`:134`) das Skript erneut startet, verdoppelt den
  Absatz in seiner eigenen Datei.
- Fix: zuerst `n_after >= 1` -> erledigt, danach `n_before == 1`.
- Sonst hält der Patch: `--check` auf der unveränderten Kopie rc 0 (6 Stellen); einmal angewendet
  (`patched1`) fielen in `test_role_contracts/test_review_procedure/test_radar_trigger/test_model_pins/
  test_shortening_net/test_presets` genau 3 von 161 Tests, und alle drei nur wegen der fehlenden `.git`
  (`git ls-files` rc 128). Dieselbe Nicht-git-Rotfärbung zeigt `test_radar_trigger` auch in der unveränderten Kopie.

### V6 -- Das office-Template behauptet "top rung is opus for every role" (Regel 3, kleiner Fix, nicht blockierend)
- `team-kits/office-team/templates/project_memory/project_config.yaml:18`: "its top rung is opus for every
  role (DEC-0078, DEC-0114 (4))". Das ist Text aus dem ersten Bau, den die Nacharbeit nicht angefasst hat.
  Auf Codex erreicht der office-developer fable. Gemessen: `office-team office-developer shipped prov=codex:
  ... 3:fable/medium`.
- Fix: "... on Claude; on Codex the office-developer climbs to fable".

### V7 -- Kit-Settings nennen auf Claude weiterhin `"model": "fable"` (benannter Rest, Löcherliste; alt, nicht aus dieser Runde)
- `team-kits/dev-team/settings/settings.json:4` und `research-team/settings/settings.json:4`: `"model": "fable"`.
  Der eigene `_comment` sagt "names the same tier the bound `agent` carries". Der gebundene
  project-manager pinnt aber `lead` = opus (`model_tiers.yaml aliases`), die Aussage ist also falsch.
- Reichweite, nach Code gelesen und nicht mit einem Prozess gemessen: Laut `_comment` gilt der Wert nur für
  Agenten ohne eigenes `model:`. Allgemeine Agenten blockt `guard_agent_spawn.py`, und
  `gen_provider_artifacts.py:810` nimmt für den Codex-Lead zuerst das `model:` der Rolle. Eine erreichbare
  Fable-Kette auf Claude habe ich nicht gefunden. Es bleibt aber der einzige Claude-seitige Wert, der fable
  nennt, gegen DEC-0114 (4) "no ... pin reaches Fable".
- Fix: `"model": "opus"` (Kit-Datei -> Stempel), oder als Loch benennen.

### V8 -- Der `--item`-Filter liest laut Docstring den ERSTEN Prompt, das hält aber kein Test (klein, nicht blockierend)
- `tools/measure_agent_tokens.py:77` gegen `tools/test_measure_agent_tokens.py`: Mutation "jede user-Zeile
  überschreibt den Prompt" (also die letzte) -> GREEN (2 passed). Im synthetischen Transkript gibt es nur
  eine user-Zeile; ein echtes Implementer-Transkript hat 387 (meist tool_results).
- Fix: dem Agenten a1 ein user/tool_result mit `TSK-0151` anhängen.
- Das Protokoll führt für dieses Skript keine Mutationen. Meine fünf anderen Mutationen waren alle RED:
  Zug = Zeile statt Id, `Start-Sleep` entfernt, "any wait" statt "every call waits", ohne
  `cache_creation`, `sleep` als Teilzeichenkette.

## Nachgerechnet und gehalten (gemessen)
- Red-first BUG-0306: `basetree` beide Knoten rot. `basetree_tbl` (nur die Tabelle von 8677bd2): Leiter-Test
  rot mit `dev-team ('project-manager', 'lead', 'normal', None): the Claude answer names fable at failed run(s) [3, 4, 5, 6, 7, 8, 9]`.
- Red-first BUG-0307: `basetree_rr` rot mit `DEC-0098 put all four on Friday ~20:00: {friday, saturday, sunday, monday}`.
- Claude-Seite: Keine Klasse, kein Pin, keine Frage und keine Eskalation bis FAIL 6 ergibt auf Claude die
  Sprosse fable. Probe über alle Rollen der drei Kits × {ausgeliefert, Frage fable, Pin fable}. Ein Spawn
  mit `model: fable` gegen einen opus-Lease wird von `spawn_model_refusal` (`dispatch.py:1146`) abgelehnt,
  nach Code gelesen.
- Codex über `ladder --provider codex`: dev/research-Architektur bei FAIL 0 fable, Builder bei FAIL 3
  fable, office-developer bei FAIL 3 fable, office bookkeeper nie. Das entspricht 8677bd2.
- Tabelle: keine Preise in den gelesenen Schreibweisen. `suited_for` gibt es für jede Sprosse × jeden
  Provider, mit URL und `read: 2026-09-25`. Die Codex-Zitate stimmen mit
  `radar/2026-09-25-codex-by-claude.md:38-41` überein, das Fable-Zitat mit `claude-by-claude.md:117-118`.
  `gen_provider_artifacts.load_tiers` liest die neuen Blöcke richtig (codex `gpt-6-astra/sol/luna`, claude
  pass-through).
- `radar_routine.py` entspricht DEC-0098 (1)-(3): alle vier Routinen Fr ~20:00, `watcher-duo` in den
  Schritten 1/2, zwei Codex-Aufgaben. `.codex/agents/*-watcher.toml`: nur die model-Zeile hat sich
  geändert (`gpt-6-sol`), und `test_every_codex_overlay_is_the_one_its_claude_definition_generates` ist grün.
- FR-0093: Die drei Zeilen stehen genau einmal je Kit (in den drei Lead-SKILLs) und widersprechen keinem
  Kit-Text (grep nach rework/resume/poll/sleep).
- `measure_agent_tokens.py --item TSK-0150` auf den echten Transkripten gibt genau die Zahlen des
  Protokolls aus (281/383 Züge, 51.568.023 / 137.484.112). Unabhängig nachgezählt (`xcheck_tokens.py`):
  581 assistant-Zeilen, 383 verschiedene Ids, 0 Ids mit abweichender input-usage, Summe 137.484.112, Median 381.612.
- Stempel: `bump_kit_version.py --check`: alle drei "unchanged" (dev -4, office -3, research -4), rc 0;
  `validate.py`: "all structural checks passed". `.claude/` ist gegenüber 8677bd2 unverändert.

## Nicht gemessen
- Volle Suite und `test_gates.py` (DEC-0050; der Lead fährt den Lieferlauf).
- `test_hooks.py`/`test_hooks_v2.py`, `test_ladder.py` als ganze Datei, `test_approvals_dispatch.py`.
- Hook-Laufzeit von `gate_dispatch` mit der zusätzlichen Tabellen-Lektüre (nach Code: eine YAML-Datei von
  9 KB pro Aufruf, nicht gemessen).
- Die Anbieterseiten selbst (die Wortlaute nur gegen die radar-Berichte geprüft).
- Ob V7 in einer echten Claude-Sitzung irgendwo greift (kein Prozess gefahren).
- `docs/PLAN_ANBIETERFREI.md` (neu, nicht im Item) nicht geprüft.

## Urteil: FAIL
Blockierend: V1 (F1 ist auf dem Dispatch-Kopf nicht geschlossen; die Texte sagen mehr als gebaut, und die
Lücke steht nicht in der Löcherliste), V3/V4 (Leser enger als ihr Docstring), V5 (Patch nicht idempotent,
obwohl zugesagt). V2, V6, V7 und V8 sind kleine Nacharbeit oder gehören als benannte Reste in die Löcherliste.
