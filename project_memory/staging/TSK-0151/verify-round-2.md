# TSK-0151 -- Prüfrunde 2 (harness-verifier)

Arbeitskopie `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0151\verify2\tree` (bytegenau, ohne .git),
dazu `verify2\patched` (Nutzer-Patch angewendet). Rig-Skripte (`copy_tree.py`, `mutate.py`, `readers.py`,
`v5.py`) verweigern jedes fremde Arbeitsverzeichnis und schreiben binär bzw. mit festem Zeilenende; die Probe
`tools/test_zz_v2_probe.py` liegt nur in der Kopie. Kein Log, kein Transkript ganz gelesen; das Protokoll nur
im Abschnitt "Rework 2", der Bericht aus Runde 1 ganz (154 Zeilen).

## Befunde

### R2-1 -- Die Eskalationshälfte von `by_provider` hat keinen Test, der scheitern kann (BLOCKIEREND)
- `team-kits/kernel/dispatch.py:3703` rechnet die anderen Anbieter mit `int(reference["failed_runs"])`.
  Der einzige Test, der `by_provider` liest (grep über `tools/`: nur `test_ladder.py:440-490`), fährt nur einen
  Architektur-Auftrag bei FAIL 0.
- Mutante M5 (`... root, 0, provider)`, also jeder andere Anbieter immer bei FAIL 0):
  `tools/test_ladder.py` ganz: **alle grün**. Im selben Lauf fiel nur der Pilot aus `test_light_kit.py`, und zwar
  am Stempel (`scaffold_error ... scaffold_team.ps1:764`), nicht am Wert.
- Der Code selbst stimmt, das habe ich gemessen (Probe, dev backend-developer, FAILED_RUNS 2 + `started`):
  Der Dispatch-Kopf zeigt `codex: rung fable, model gpt-6-astra, effort high`.
- `team-kits/model_tiers.yaml:86-94` behauptet "the escalation reach `fable` ... which the lease and the
  dispatch header carry" und nennt dafür genau diesen Test. Der Test kann für die Eskalation nicht scheitern.
  Das verstößt gegen Regel 4/5, und die Eskalation ist die halbe Anforderung aus F1.
- Fix: Im selben Test einen Builder-Auftrag bei FAIL 3 ergänzen: `codex` = fable/gpt-6-astra, `claude` = opus.

### R2-2 -- `ladder` ohne `--provider` zeigt die Karte des LETZTEN Leases, nicht die des nächsten (BLOCKIEREND, gleiche Stelle)
- `team-kits/kernel/cli.py:2029-2033` hängt `by_provider` an die Antwort beim aktuellen Zählerstand. `next_lease`
  (`:2026-2028`) bekommt keine Karte. Der Kommentar sagt "the map the dispatch header carries", das Protokoll
  "`ladder <TSK>` WITHOUT `--provider` prints the same map".
- Gemessen (Probe, FAILED_RUNS 2 + `started`):
  `ladder rc=0 by_provider={... "codex": {"effort": "xhigh", "model": "gpt-6-sol", "rung": "opus", ...}} next_lease_counts=3`,
  danach `dispatch header by_provider={... "codex": {"effort": "high", "model": "gpt-6-astra", "rung": "fable", ...}}`.
- Folge: Genau im Moment der Codex-Eskalation zeigt der Befehl, den die Verfassungen nennen, die alte Stufe.
- Fix: `answer["next_lease"][PROVIDERS_KEY] = ladders_by_provider(state, pending, root, answer["next_lease"])`,
  dazu ein Fall im Test aus R2-1.

### R2-3 -- Der Preis-Leser: ein Quantor-Fehler gegen die eigene Definition (a BLOCKIEREND, b Kommentar einengen)
- a) `tools/test_model_ladder.py:120`: `%(amount)s?` ergibt `\d[\d.,]*?`. Das `?` macht nur das `*` faul, der
  Betrag hinter "per" ist also PFLICHT. Die Definition (`:108-113`) sagt dagegen "an amount PER A COUNT OF TOKENS".
  Gemessen: `'2 per million input tokens' -> []`, `'15/75 per million' -> []`, `'15 per M' -> []`,
  `'15 input / 75 output per 1M' -> []`.
  Die Korrektur `(?:%(amount)s)?` (Mutante M8) lässt die Datei grün: Der bug_0306-Knoten ist grün, rot wird nur
  der .git-abhängige Knoten, und der ist es auch ohne Mutante.
- b) "a currency's name after it" wird nur ohne Zwischenwort gelesen: `'15 US dollars' -> []`, `'15 Swiss francs' -> []`.
  Klein geschriebene ISO-Codes (`'usd 15' -> []`) liest der Leser absichtlich nicht.
- Falsch-positiv (heute nicht in der Datei, gemessen am Leser): `'Codex CLI 0.131' -> ['CLI 0.131']`, `'GPT6'`,
  `'API 2'`, `'USE 4'`. Der Grund ist das ISO-Muster "drei Großbuchstaben + Zahl". Dazu kommen aus den
  Unicode-Namen `'2 marks'`, `'4 colons'`, `'1 currency'`, `'3 mill'` sowie `'per token context'`.
  Nach Regel 3 muss der Kommentar diese Nebenwirkung nennen.
- Gehalten: Die Leser-Mutanten des Umsetzers sind nachgefahren und ROT (M6 ohne Namen, M7 ohne Id-Teile).

### R2-4 -- Der Leser für verneinte Zeilen zählt Verneinungen auf, statt sie zu definieren (Regel 1/3; Kommentar einengen oder erweitern)
- `tools/test_model_ladder.py:139` (`DENIAL_RX`: no|not|never|none|without) gegen den Kommentar `:128-137`
  ("a negation word", "A name is any word").
- Gemessen nicht gelesen: `"there isn't a luna row"`, `'there is no haiku/luna row'` (der ursprüngliche Satz,
  nur mit `/`), `'no luna-class row'`, `'zero luna rows'`, `'the table lacks a luna row'`, `'luna has no row'`.
- Falsch-positiv bei WAHREN Sätzen: `'no claude row names gpt-6-luna'` und `'no row carries a price, opus included'`
  werden gemeldet.
- Fix: Wörter zusätzlich an `/` und `-` teilen und `n't` aufnehmen, oder den Kommentar auf die gelesenen Formen
  einengen und die nicht gelesenen nennen.

### R2-5 -- `installed_providers`: drei Docstring-Eigenschaften, die der genannte Test nicht hält (klein, Regel 4)
- `team-kits/kernel/dispatch.py:360-385`. Mutanten auf dem benannten Testknoten, alle **grün**:
  - M1: die Referenz nur, wenn gelistet.
  - M2: eine unlesbare Konfiguration liefert nur die Referenz.
  - M3: kein `.strip().lower()`.
- Das Verhalten stimmt, gemessen per Probe: `[codex]`, `[Claude,' Codex ']`, Skalar, `[]`, null, kaputtes YAML
  und `project.providers` liefern beide Anbieter; `[openai]` liefert nur claude. Genau das sagt der Docstring.
- Fix: Die Fälle `[codex]` und kaputte Konfiguration in den Test aufnehmen.

## Nachgerechnet und gehalten (gemessen)
- V2: Auf Claude liefern Frage und Pin `fable` bei FAIL 0-7 dasselbe wie ohne Frage/Pin, in allen drei Kits
  (dev backend-developer, research methodologist, office office-developer). Beispiel `FAIL 0: opus/high` ×3;
  office bei FAIL 0 `opus/medium` ×3. Claude erreicht nie fable.
- Codex erreicht astra: Architektur FAIL 0 fable/gpt-6-astra, Builder FAIL 3 fable, office-developer FAIL 3 fable.
- V5: `--check` rc 0 "6 site(s)" / Anwenden "DONE -- 6" / `--check` "0 site(s)" / Anwenden "DONE -- 0".
  Danach Absatzzahl 1, `effort: xhigh` 1, CRLF 0; Watcher ohne Saturday/Sunday/Monday.
  `test_gates.py -k "agent or spawn or gate2 or lead or measurement or session or role or effort"` auf dem
  gepatchten Stand: **233 passed, 322 deselected in 669.73s**.
- V6: Der Text stimmt jetzt. V7: `"model": "opus"` in allen drei Kits, dazu der Test. V8: die Mutanten "jede
  user-Zeile überschreibt" (M9) und "alle user-Zeilen verkettet" (M10) sind beide ROT.
- H221/BUG-0308 ist ehrlich: `lease_rung`/`lease_effort` liest außer `create_lease` nur `kernel/report.py`
  (grep). Mechanismus, Kette und Grenze stehen im Item.
- Stempel: `bump_kit_version.py --check` rc 0, dev -5 / office -4 / research -5 "unchanged". FR-0093: drei Zeilen,
  genau einmal je Kit (nur die Lead-SKILLs). `radar_routine.py` und `.codex/agents` sind seit Runde 1 unverändert
  (diff der Runde-1-Kopie gegen jetzt), die Messung aus Runde 1 gilt also weiter.

## Nicht gemessen
- Volle Suite; `test_gates.py` ganz; `test_approvals_dispatch.py`; `test_hooks*.py`.
- Hook-Laufzeit. Nach Code rechnet `by_provider` nur `kernel.cli dispatch`/`ladder`, am Spawn wird nichts
  zusätzlich gelesen; gemessen habe ich das nicht.
- Ob die Codex-CLI ein Modell je Spawn wählen lässt; `docs/PLAN_ANBIETERFREI.md`.
- Neue `.ruff_cache/0.16.9` unter `team-kits/*/templates/repo/`: gesehen, nicht untersucht (der Stempel ignoriert sie).

## Urteil: FAIL
Blockierend: R2-1 und R2-2, denn die Eskalationshälfte von F1 auf dem `by_provider`-Pfad ist weder getestet noch
im `ladder`-Befehl richtig. Dazu R2-3a, ein Ein-Zeichen-Fehler gegen die eigene Definition. R2-3b, R2-4 und R2-5
sind kleine Text- und Testnacharbeit und gehören in denselben Gang. Sonst wird jede davon ein benannter Rest in
der Löcherliste, mit dem Mechanismus "Leser liest nur angrenzende/aufgezählte Formen".
