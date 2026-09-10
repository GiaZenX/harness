"""Capture the user's addendum of 2026-09-10 to DEC-0077 / DEC-0088: with several builders in parallel the PM
assigns EACH work order its own rung and effort by the slice's scope and the judgment it needs (sonnet /
opus / fable x high / xhigh) -- today every build role runs on the same pin. Body on stdin to
`kernel.cli capture DEC`; carrier = generation 6's goal (like DEC-0087/0088), `work` set at that capture.
Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Stufe je AUFTRAG (Zusatz zu DEC-0077 / DEC-0088): bei mehreren parallelen Bauern gibt der PM jedem "
             "Arbeitsauftrag seine eigene Sprosse und seinen eigenen Aufwand nach Umfang und noetigem Urteil -- sonnet / "
             "opus / fable mal high / xhigh -- als dritte Eingabe der Sprossen-Ableitung, nie unter dem Boden der Rolle",
    "context": "USER 2026-09-10 23:0x: 'wenn wir parallele Subagents haben waere es schlau, dass der PM je nach "
               "Aufgabenumfang und Intelligenzniveau jedem der mehreren Backend-/Frontend-Devs mehrere Modellstufen "
               "gibt -- bisher haben alle die gleichen? Der PM muss sagen: der eine passt nur x an -- sonnet high/xhigh; "
               "der andere arbeitet y ab, komplexer -- opus high/xhigh; der dritte macht z, extrem viel Aufwand, "
               "Feinarbeit, Bewertungspotenzial -- fable high/xhigh.' MEASURED on the merged tree (TSK-0133, "
               "2026-09-10): the user is right -- every build role of dev-team pins `model: worker` (= sonnet) at "
               "`effort: high` (backend-developer.md:5, frontend-developer.md:5, devops-engineer.md:5, "
               "research-engineer.md:5); dev-team/ladder.yaml derives the RUNG from the role's class (planning/"
               "architecture: top, design/qa: opus, build: pin) and the EFFORT from the goal's class (default high, "
               "large xhigh); escalation climbs one rung per FAILED run (DEC-0034 rule 2). The PM has NO per-order "
               "input: two build orders under one goal always start on the same rung and effort, however unequal "
               "their slices. DEC-0088 (1)/(2) already say the orchestrator derives 'goal-sized -> top rung, mechanical "
               "slice -> lower rung' -- but only per GOAL and with no field to carry it; `create-task` has no --rung / "
               "--effort option and the TSK contract no such field.",
    "decision": "(1) A work order (TSK) carries two optional fields, `rung` and `effort`, set by the PM at create-task "
                "(and changeable while DRAFT): the PM's judgment of the slice -- mechanical edit with a complete spec "
                "-> sonnet; complex work with design room -> opus; large, fine, judgment-heavy work -> fable; effort "
                "high by default, xhigh where the PM names why (DEC-0088 (4): a named step, never a standing setting). "
                "(2) The dispatcher (kernel create_lease and the kit dispatch path) derives the lease's rung as the "
                "HIGHER of the ladder's class/pin rung and the order's `rung`, the effort as the higher of the goal's "
                "effort and the order's `effort` -- the role's floor and the kit's ladder stay the floor (a PM can lift "
                "an order, never lower a role below its class; office's floors stay DEC-0078's), escalation on FAIL "
                "still climbs from wherever the order starts, `top` still caps. (3) Both values stand on the lease and "
                "in the session brief (PR-0010 AC-6) and in the check-scopes output beside the order, so two parallel "
                "orders show their two rungs side by side; a test refuses an order rung outside the kit's ladder "
                "vocabulary and an effort outside low|medium|high|xhigh. (4) The PM's duty text (project-manager skill "
                "+ constitution) names the three-line rule in the user's words and the one question it must NOT ask: "
                "the user is never asked for tiers (DEC-0088). (5) CARRIER: generation 6's goal (the light kit), where "
                "the builder/order tiers are cut anyway; DEC-0087 (7) and DEC-0088 sit on the same carrier. (6) The "
                "codex side follows through model_tiers.yaml (astra / sol / terra) with no second table.",
    "consequences": "Parallel builders cost what their slice needs, not what the role pin says; the strongest model "
                    "goes where judgment is bought, the cheapest where a spec is executed -- the user's rule made "
                    "mechanical. Cost: two fields in the TSK contract, one max() in the dispatcher, one brief line, "
                    "three tests. Rejected: asking the user per order (DEC-0088), a per-role second pin (the role is "
                    "not the unit -- the order is), lowering a role below its class (the ladder's floors are measured "
                    "against pilots and stay).",
    "work": ["PR-0011"],
    "source": "user message 2026-09-10; team-kits/dev-team/agents/*.md pins; team-kits/dev-team/ladder.yaml; DEC-0077; "
              "DEC-0078; DEC-0088; DEC-0034; kernel.cli create-task --help (no rung/effort option, measured 2026-09-10)",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
