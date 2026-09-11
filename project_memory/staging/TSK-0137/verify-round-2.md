# Prüfbericht TSK-0137 — Runde 2 (B1, N-a, N-b, N-c) — **PASS**

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead hierher gelegt (2026-09-11 11:3x, Uhr gelesen).
Frische Kopie, `git init`, Stempel `2026.09.11-10` ×3, `bump_kit_version.py` unchanged ×3. Uhr 11:30:36. Rig
`…\TSK-0137\verify\vrig2.py`, Bericht `vrig2-report.json`.

## B1 — BEHOBEN
Gegen `dispatch.acceptance_is_test_shaped`: `docs/test-plan.md` False · `docs/manual-test-notes.md` False ·
`docs/testimonials.md` False · `tools/test_x.py` True · `'no test needed for this rename'` False · `'kein Test
noetig'` False · `'tests are not required here'` False · `'a test goes red without the fix'` True. Eigene
Formulierungen — abgelehnt (korrekt): „Fuer diese Umbenennung ist kein Test noetig …", „the document describes our
test strategy for later", „the rename is done; no test goes red after it", „the build passes", `docs/testing/
overview.md`, `src/attest.py`, `notes/test.md`; gewährt (korrekt): „run pytest tools/test_y.py and it stays green",
„::test_rename_keeps_the_pin passes", „der Test schlägt fehl, bis der Fix da ist", `tests/renames/x.py`,
`pkg/x_test.go`, `web/x.test.ts`, `spec/x_spec.rb`. Rig: W14/W15 (Wort-Leser zurück) rc 1; **W16** (nur die
Negationswache entfernt) `AssertionError: (…, 'no test goes red after this rename')`; W17 (Modulkonvention
gelockert) `['lib/x_spec.rb']`; W18 (Urteilspflicht weg) `'a test plan is written'`.

## N-a / N-b — BEHOBEN
W20 (= V6, Klemmung entfernt) rc 1 `{'rung': 'sonnet', … 'kit': 'inverted', …}`; W21 (why echot das Dateiwort) rc 1;
ungemutet `class build starts on opus (declared pin)`. Träger
`test_a_declared_pin_default_is_clamped_up_to_the_floor_and_the_answer_says_the_clamped_rung`.

## N-c — WAHR gegen den Code
Jedes Beispiel der sechs Texte nachgemessen (`'the regression test goes red'` True, `'der Test wird rot'` True,
`'kein Test nötig'` False, die vier Modulkonventionen + `tests/` / `test/` True, `docs/test-plan.md` False); alle
sechs nennen `dispatch.acceptance_is_test_shaped` als Autorität. Office unverändert.

## Eigener Fehlschlag des Prüfers, offen gesagt
W19 („ein Urteilswort entfernt") blieb grün — richtig so: ein entferntes Wort macht das Vokabular enger (sichere
Richtung). Die Richtung, die der Docstring verneint (totes/redundantes Wort), nachgefahren: W22 Duplikat rc 1
(„'red' … carries no sentence"), W23 subsumiertes Wort rc 1 („'turns red' earns nothing"). Der Stolperdraht hält beide
Enden.

## NEU (nicht blockierend, beide in der SICHEREN Richtung — Falsch-Negativ, der Auftrag bleibt auf opus)
**N-e** `_DENIES_RX` führt `ohne`, aber nicht `without`: „ein Test wird rot, ohne den Fix" → False, „a test goes red
without the fix" → True — die Rot-zuerst-Formel dieses Repos auf Deutsch abgelehnt. Fix: `ohne` streichen (Präposition,
kein Verbnegator) oder die Verneinung an den Teilsatz binden; Zeile im Zwei-Enden-Test.
**N-f** `_WORD_TEST_RX`: deutsche Komposita unsichtbar („der Regressionstest schlägt fehl" → False, „der Unittest wird
rot" → False). Fix: Kommentarzeile für Deutsch oder `\w*tests?\w*` nur für die Urteils-Variante.
Mechanismus beider: *Verneinungs- und Wortliste sind einsprachig ausgelegt, der Leser beansprucht zwei Sprachen.*

## Läufe
`test_ladder` 48 · `test_light_kit` 26 · `test_role_contracts` 32 · `test_review_procedure` 27 · `test_model_ladder` 13
— je einzeln grün; ruff, validate clean; Stempel unverändert ×3. Nicht gemessen: eigene Hook-Prozesse, `test_report`/
`test_schemas` (Runde 1 grün, unberührt), kein voller Lauf.

## Urteil
**PASS.** B1 geschlossen (sechs benannte + sieben eigene Formulierungen richtig, fünf Mutationen rot), N-a/N-b je mit
rotem Test, N-c wahr. N-e/N-f benannte Restposten (Loch-Item), keine dritte Runde.
