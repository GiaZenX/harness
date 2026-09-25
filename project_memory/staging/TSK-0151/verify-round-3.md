# TSK-0151 -- Prüfrunde 3 (harness-verifier), eng: R2-1 .. R2-5

Arbeitskopie `C:\Offline Repos\v2-testbed\_round-scratch\TSK-0151\verify3\tree` (bytegenau, ohne .git und Caches,
`copy_tree.py`), dazu `tree2` für Proben. `mrun.py` ersetzt binär genau ein Vorkommen je Stelle, fährt den
benannten Knoten und setzt zurück. Es verweigert fremde Arbeitsverzeichnisse (DEC-0070), sein Ergebnis steht in
`mrun.out`. Gelesen habe ich: das Protokoll nur im Abschnitt "Rework 3", den Bericht aus Runde 2 ganz (98 Zeilen)
und BUG-0309 ganz (41 Zeilen). Kein Log ganz gelesen. Die Änderungen von Rework 3 ergeben sich aus
`diff -rq verify2/tree verify3/tree`: `cli.py`, `dispatch.py`, `test_ladder.py`, `test_model_ladder.py`, drei
VERSION-Dateien und Zustand.

**Eigener Fehler, offen benannt:** Mein erstes `mrun.py` hat bei zwei Stellen in derselben Datei in falscher
Reihenfolge zurückgesetzt. Die erste Stelle von M1 blieb stehen, und der Stempel-Check in der Kopie meldete
deshalb "BUMP DUE". Diese Mutante ist äquivalent, weil die Referenz ohnehin vorangestellt wird. Ich habe das Rig
korrigiert (`reversed(done)`), die Datei aus dem Repo hergestellt und alle Mutanten neu gefahren. Die Ergebnisse
sind identisch, und die Kopie ist danach gleich dem Repo (`diff -rq`, nur `.ruff_cache`/`.pytest_cache`).

## Befunde

### F3-1 -- Der Kommentar zum Preis-Leser nennt die Falschtreffer-Klasse nicht, die der R2-3a-Fix selbst geöffnet hat (klein, Regel 3)
- `tools/test_model_ladder.py:118-119` ("READ although no price: three capitals ..., a word a currency sign's
  Unicode name happens to carry ... and "per token"") und entsprechend `BUG-0309` `observed`.
- Das `(?:%(amount)s)?` in `:128` macht die Zahl hinter `per`/`/` optional. Seitdem liest der Leser einen Betrag
  vor einem nackten Größenwort als Preis. Gemessen, alte Leser aus `verify2/tree` gegen den heutigen:
  `'a 3/k split' [] -> ['3/k']`, `'1 / M' [] -> ['1 / M']`, `'5 per k' [] -> ['5 per k']`,
  `'8 / thousand' [] -> ['8 / thousand']`.
- Außerdem steht nur "per token" da, der Schrägstrich derselben Alternative (`:126`) fehlt:
  `'see docs/tokens.md' -> ['/tokens']`. Das war schon in Runde 2 so, genannt wurde es aber nie.
- Genau das verlangt die Entscheidung des Leads zu R2-3b: der Kommentar muss wahr sagen, welche Nicht-Preise
  gemeldet werden. Die Folge ist gering, denn ein Falschtreffer macht den Test laut rot. Die heutige Datei hat
  keinen Treffer.
- Fix (Text): Im Kommentar und in `BUG-0309 observed` je einen Satzteil ergänzen: "an amount before `per`/`/`
  and a bare magnitude (`3/k`, `5 per k`), and `/token` (a path `docs/tokens.md`)".

### F3-2 -- `installed_providers`: "carries no list" ist beim Skalar nicht gehalten (klein, Regel 4, dieselbe Klasse wie R2-5)
- `team-kits/kernel/dispatch.py:367-368` sagt "A config that ... carries no list answers EVERY row".
- Der Test `tools/test_ladder.py:541-549` hat nur die Fälle "fehlender Schlüssel", "leere Liste" und "keine
  Datei". Einen Skalar prüft er nicht.
- Mutante M16 (`named = [named] if isinstance(named, str) else named`) bleibt grün:
  `M16 rc=0 | 1 passed`.
- Das Verhalten selbst stimmt. Der Beweis für den Fix ist gemessen: Mit der Zeile
  `("a scalar", "providers: %s\n" % reference, every)` ist der echte Code grün (`CASE rc=0`) und M16 rot
  (`CASE_M16 rc=1 AssertionError: a scalar ... ('claude',) == ('claude', 'codex')`).
- Fix: diese eine Zeile in den Test aufnehmen.

## Gehalten (gemessen)
- **R2-1** Knoten `test_the_lease_and_the_header_carry_..._bug_0306`, Baseline `1 passed`. Die Mutante M5 aus
  Runde 2 (`root, 0, provider`) ist ROT: `the map at the old count equals the climb`. Meine eigene M12
  (andere Anbieter eine Zählung zurück) ist ROT, dieselbe Zeile.
- **R2-2** Meine eigene M11 (Karte von `next_lease` aus der alten Antwort gerechnet) ist ROT. M11b aus dem
  Protokoll (Schleife nur über `(answer,)`) ist ROT mit `(None, {...})`.
- Eigene Probe über die echte CLI, `ladder` und danach `dispatch`, FAIL 0..5 bei dev backend-developer, dev
  software-architect, research methodologist, research researcher und office office-developer:
  **30/30 `equal True`**. Die Karte von `next_lease` (ab FAIL 1) bzw. die oberste Karte (bei FAIL 0) ist gleich
  dem `by_provider` des folgenden Kopfs.
  - **Claude erreicht nie fable** (30× `claude opus/...`).
  - **Codex erreicht astra**: Builder und office-developer bei FAIL 3
    (`codex fable/gpt-6-astra/high` bzw. `/medium`), Architektur und methodologist ab FAIL 0.
- **R2-3a** `'2 per million input tokens' -> ['2 per million']`, `'15/75 per million' -> ['75 per million']`.
  M8r (Quantor zurück) ist ROT: `2 per million input tokens`. Meine eigene M18 (ohne `million`) ist ROT.
  `model_tiers.yaml hits: []`. 13 ehrliche Herstellerzeilen (etwa `'up to 1M tokens of context'`,
  `'128K max output tokens'`, `'1M-token context'`) ergeben keinen Treffer. Die Ausnahme ist
  `'lower cost per token'`, und die ist genannt.
- **R2-3b** Alle im Kommentar genannten Grenzen sind in beiden Richtungen so gemessen, wie der Kommentar sagt.
  BUG-0309 hat `limits` auf Deutsch, severity low und `repro` wie angegeben. Das Zitat von DEC-0102 (2) stimmt
  mit der Entscheidung überein.
- **R2-4** Der Leser ist weg: `DENIAL_RX`, `denied_carried_rows` und `_flat` kommen in `tools/`, `team-kits/`,
  `.claude/`, `docs/` und im kanonischen Zustand nicht mehr vor. Die beiden Treffer sind der ältere
  `_SURFACE_DENIAL_RX` in `test_hooks.py`, und der liegt nicht im Diff. Auch der alte Testname kommt nirgends
  mehr vor. Der Docstring des Tests sagt "no reader of prose negation holds it", und das ist wahr. Der Satz in
  der Stufentabelle (`:17-18`, seit Runde 2 unverändert) stimmt heute.
- **R2-5** M1 ist ROT (`listed without the reference`), M2 ROT (`unreadable`), M3 ROT (`spelled loosely`).
  Meine eigenen Mutanten sind ebenfalls ROT: M14 (kürzt nicht) und M14b (vergleicht Groß-/Kleinschreibung).
  M15 (leere Liste als Liste gelesen) ist ROT mit `empty list`. Der Generator normalisiert ebenfalls mit
  `strip().lower()`, wie der Docstring sagt.
- Stempel: `bump_kit_version.py --check` im Repo und in der sauberen Kopie ergibt dev -6, office -5 und
  research -6, jeweils "unchanged". `validate` rc 0, `0 error(s), 56 warning(s)` (verwaiste Staging-Ordner).
  `ruff 0.15.20 check` über die vier Dateien: "All checks passed!".

## Nicht gemessen
- Volle Suite und `test_gates.py`, wie beauftragt (die fährt der Lead).
- Andere Knoten in `test_ladder.py` und `test_model_ladder.py` außer den vier benannten.
- Die Laufzeit von `ladder`. Die Karte wird jetzt bis zu zweimal gerechnet, aber das ist kein Hook.

## Urteil: FAIL -- nicht blockierend
Die fünf Fixes halten, gemessen gegen die Entscheidungen des Leads, und keine Mutante aus Runde 2 überlebt.
F3-1 und F3-2 sind je eine Zeile Text bzw. Test und gehören in denselben Gang. Werden sie nicht gemacht, müssen
sie benannt stehen bleiben: F3-1 in `BUG-0309 observed`, F3-2 als Rest mit dem Mechanismus "Test liest eine
Form von 'no list' weniger, als der Docstring verspricht". Code und Anbieter-Leiter sind korrekt.
