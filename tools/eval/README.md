# Harness output-quality eval (v1 skeleton)

Deterministic gates (tools/test_hooks.py, validate.py) prove the MACHINERY works; this eval judges
the QUALITY of specialist outputs — the Anthropic pattern: canonical scenarios + an LLM judge
scoring 0.0–1.0 per criterion with a pass/fail verdict.

## v1 scope (honest)
`scenarios.yaml` ships 10 canonical work orders with per-scenario `must_have` properties. The run
is MANUAL for now (below); CI wiring is deferred until the scenario set has settled — a moving
rubric in CI would just train noise.

## How to run (manual)
1. Pick a scenario; scaffold a throwaway repo with the scenario's kit (`scaffold_team.ps1 -Team …`).
2. Seed the minimal project_memory named in `read_first` (small, realistic content).
3. Start a session and have the lead delegate the scenario's `work_order` verbatim to the role.
4. Judge: paste the specialist's full output + the scenario's `must_have` list into a FRESH
   Claude session (opus) with:
   "Score each must_have 0.0–1.0 with one evidence line, then overall pass/fail. A property that
   is claimed but not evidenced in the output scores <= 0.3. Be strict; no partial credit for
   intentions."
5. Record results in this folder as `runs/<date>-<id>.md` (scores + judge quotes). Two consecutive
   fails on a scenario = a harness issue -> open a hardening-round item.

## Extending
Add scenarios when a REAL failure class appears (each `must_have` should trace to an observed
failure, like the shipped ones do) — not speculatively. Target ~20, then revisit CI wiring.
