# Prüfbericht TSK-0136 — Runde 2 (nur F1–F5) — **PASS**

Prüfer: `harness-verifier` (Opus, high). Als Text geliefert, vom Lead unverändert hierher gelegt (2026-09-11 10:3x,
Uhr gelesen). Frische Kopie ohne `.git` (`robocopy /MIR`, `git init` dort). Uhr gelesen 10:22:50. Stempel im Baum
`2026.09.11-8` ×3, `bump_kit_version.py` → unchanged ×3 in der Kopie.

## F1 — BEHOBEN
`team-kits/kernel/dispatch.py:2910/2959` — Reset hängt an den **gewährten** Sprossenschritten. Sonden neu gefahren:
`DEV FAIL 5 -> fable xhigh, FAIL 6 -> fable xhigh` · `OFF FAIL 5 -> opus high, FAIL 6 -> opus high` · DEV/OFF FAIL
0..9: der Aufwand ging NUR bei 2→3 runter (Sprosse gewährt, also bezahlt). Äquivalenz unterhalb des Deckels auf einer
eigenen 6-Sprossen-Leiter (FAIL 0..17): jeder Effort-Rückfall fällt exakt mit einem gewährten Sprossenschritt zusammen
(2→3, 5→6, 8→9, 11→12, 14→15), danach wieder aufwärts. Vier eigene Mutationen, alle rot:

| Mutation | Knoten | Schiedsrichterzeile |
|---|---|---|
| V1 (=R9) `failed_runs % per_rung` zurück | `test_a_failed_run_raises_the_effort_before_it_raises_the_rung` | `FAIL 9 came back on the same rung r3 at a WEAKER effort than FAIL 8 (high -> low)` |
| V2 `granted_rungs = failed_runs // per_rung` | dito | `FAIL 9 … (high -> low)` |
| V3 `>=` → `>` in `walk_the_failed_runs` | dito | `FAIL 9 … (high -> high)` |
| V4 Satz zählt wieder die abgeleiteten Schritte | `test_an_order_that_failed_climbs_one_rung_per_failed_run_capped_at_the_top` | `FAIL 3: rung +3, effort +0 …` |

V1 wird von der **Eigenschaftszusicherung** gefangen, nicht von den Literalzeilen (Selbstkorrektur des Prüfers: beim
ersten Lesen für redundant gehalten; V1 und V3 zeigen das Gegenteil). Die fünf Texte stimmen am Deckel
(`dispatch.py:2940-2947`, drei `ladder.yaml` „THE RESET IS PAID FOR BY THE RUNG STEP", dev `:415-421`, research
`:387-393`, office `:464-470`).

## F2 — BEHOBEN
`tools/test_ladder.py:251-256`: drei Aufwandsschritte, zwei Sprossenschritte unter `top`, „three rungs and not six ON
PURPOSE, because the cap has to be REACHABLE inside a test" — gemessen richtig: auf sechs Sprossen hätte der
Runde-1-Defekt erst bei FAIL 18 gefeuert, auf drei bei FAIL 9.

## F3 — BEHOBEN
`tools/test_hooks.py:6091-6095`: `nie gefragt` → NO HITS; `no team-size question` → `office-manager/SKILL.md` ×1, dort
Subjekt False / Ask False. `-k team_size`: 2 passed, 1019 deselected — die zwei sind genau die Leser des Vokabulars.

## F4 — BEHOBEN
`.claude/agents/harness-lead.md:13-19` begründet über die `agent:`-Bindung; das Zitat steht wortgleich in
`CLAUDE.md:184`, die Gegenaussage aus `:186` wird getragen.

## F5 — BEHOBEN
`VERSION` ×3 `2026.09.11-8`; `rig-report.json` rows 10 red 10 | nodes 8 rc0 8; §6 neun Residuen; Kopfzeile, §4 und
beide EVD-Summaries nennen −8, 10/10, 8/8.

## Läufe
`test_ladder` 39 (43 s) · `test_light_kit` 26 (119 s) · `test_role_contracts` 32 · `test_review_procedure` 27 ·
`test_hooks -k team_size` 2 · `ruff check tools team-kits` · `validate.py` — alle grün; dazu `test_model_ladder` +
`test_model_pins` 18 passed (N1).

## NEU (nicht blockierend)
**N1** `protocol.md:90-91`: „neither reads a file the rework touched" ist für beide Suiten falsch (`test_model_ladder`
liest Leitern, Verfassungen, VERSION; `test_model_pins` liest `harness-lead.md`) — gefahren: 18 passed; falsch ist
die Begründung der Auslassung. **N2** `dispatch.py:2941-2942` „the effort STAYS at the ceiling" — gemessen auf sechs
Sprossen: bleibt bei `min(default + effort_steps_before_rung, ceiling)`, nicht an der Decke; auf den drei Kits fällt
beides zusammen. Beide Einzeiler für die nächste Berührung (TSK-0137).

## Nicht gemessen
Keine echten Hook-Prozesse gegen ein eigenes Projekt; kein voller `tools/`-Lauf; `harness-lead.md` `model: opus` von
innen unmessbar; DEC-0095 (1) „every kit" gegen „office unchanged" = Lead-/Nutzersache.

## Urteil
**PASS.** F1–F5 behoben, je eigene Messung, F1 gegen vier Rückmutationen. N1/N2 benannt, keine dritte Runde.
