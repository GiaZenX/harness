# Prüfbericht TSK-0137 — Runde 1 — **FAIL** (ein blockierender Befund)

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead hierher gelegt (2026-09-11 11:2x, Uhr gelesen;
der Umsetzer hatte die Nacharbeit aus der Nachricht des Leads genommen, weil diese Datei zu dem Zeitpunkt noch
fehlte — Lead-Versäumnis, im Rundenlog benannt). Kopie ohne `.git` unter
`C:\Offline Repos\v2-testbed\_round-scratch\TSK-0137\verify\repo`, Rig `…\verify\vrig.py`, Uhr 11:01:31 / 11:10:43.
Stempel `2026.09.11-9` ×3, `bump_kit_version.py` unchanged ×3.

## B1 — BLOCKIEREND: der Test-Leser liest das WORT, nicht die Aussage
`team-kits/kernel/dispatch.py:2849` `_NAMES_A_TEST_RX = re.compile(r"(?<![a-z0-9])tests?(?![a-z0-9])", re.IGNORECASE)`.
Gemessen auf der ausgelieferten dev-Deklaration (echte `create_lease`): AC-Text `'no test needed for this rename'`,
Bitte sonnet → `rung=sonnet`, why „allowed: the acceptance is a test"; `expected_outputs ['docs/test-plan.md']` →
ebenso. Leserproben: `'kein Test noetig'` True · `'tests are not required here'` True · `docs/manual-test-notes.md`
True; `docs/testimonials.md`, `docs/latest.md`, `src/x/unittest.py` False. Falsche Behauptung in Lease, Checkpoint (c),
`dev/skills/project-manager/SKILL.md:247`, `research…/SKILL.md:153`, `dev/constitution/AGENTS.md:410-411`. Kein Test
misst die verneinte Richtung. Vorbild im Repo: `tools/test_hooks.py::_team_size_questions` (satzweise, Subjekt +
Ask + Negationsvokabular). Kein Sicherheitsloch (derselbe PM schreibt Bitte und Abnahme). Wege: (1) satzweiser Leser
+ rote Zeilen je Richtung; (2) ehrlicher Satz + Loch. **Lead: Weg 1.**

## Gemessene negative Befunde
12 eigene Mutationen, 11 rot (V1–V3 Paar/Skalar-Stolperdraht beidseitig; V4 Test-Bedingung immer wahr; V5 Boden-
Verweigerung; V7 Band ignoriert; V8–V10 Validator-Verweigerungen; V11 Verteilung nur Sprossen; V12 ein Zeichen in
der Prüfer-Kopie) — **V6 (Klemmung `default = max(floor, …)`) GRÜN** → N-a. Ableitung auf dev/office richtig (ohne
Bitte opus; über Default `max()` mit `top`; unter dem **Boden** verweigert „a floor is not a band"; office sonnet ohne
Band-Satz); invertiertes Paar geklemmt; Checkpoint (c) + `CHECKPOINT_QUESTION` mit beiden Signalen wörtlich (gegen
research A §3 geprüft); `gate_dispatch.py` ×3 byte-identisch, unverändert gegen e0e515f; Verteilung beide Achsen;
Lesedisziplin ×3 `d696f71a18629eca` und in beiden Repo-Rollentexten `67b816f4369ee1e8`; N2 umformuliert; Residuum 8:
die Runde-2-Notiz des Prüfers war die ungenauere (20,9 s Wanduhr / 19,3 s API gemessen). Suiten einzeln grün: 45 /
26 / 126 / 30 / 5 / 32 / 27 / 13; ruff, validate, Paketgrößen stimmen.

## NEU (nicht blockierend)
N-a `dispatch.py:2963` Klemmung ungemessen (V6 grün) → Fixture `{default: pin, floor: opus}`. N-b `:2964` why echot
das Dateiwort statt des aufgelösten Werts. N-c Verfassungen „under `tools/`" enger als der Code. N-d der Pilot misst
(b) und office, (a) nur in der Fixture.

## Nicht gemessen
Keine eigenen Hook-Prozesse; kein voller Lauf; `test_gates.py -k` des Umsetzers nicht nachvollzogen; (g)-Zahlen.

## Urteil
**FAIL** — B1 als Behauptungs-Defekt (Mechanismus: Wortvorkommen ohne Verneinung), N-a–N-d benannte Restposten.
