"""Capture the user's decision of 2026-09-11 07:1x: the builder default is OPUS; Fable is not sustainable as a
standing tier (30 % of the weekly Max-20 usage in 8 h, measured on this session). Answers the open tier question of
DEC-0087 (7) / DEC-0088 (1) without the experiment; says WHEN Fable. Body on stdin to `kernel.cli capture DEC`,
work = PR-0011. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Bauer-Standard OPUS (loest DEC-0088 (1) 'top rung' ab): Fable ist als Dauerstufe nicht tragbar; Fable nur "
             "noch fuer den benannten Architektur-Schritt eines grossen Ziels und als Eskalationsziel nach einem "
             "gescheiterten Opus-Bau -- Orchestrator/PM, Bauer und Pruefer laufen auf Opus",
    "context": "USER 2026-09-11 ~07:00: 'In den letzten 8 h 30 % meiner Weekly Usage verbraucht (Max-20), es lief nur "
               "diese Session -- das ist brutal, effizient ist es so sicher nicht.' Then: 'Ja, Bauer-Standard auf Opus "
               "setzen bitte. Fable ist nicht tragbar. Dann muss das eben gut orchestriert und ueberwacht werden, dass "
               "er seine Aufgabe fertig macht. Opus Standard -- und wann Fable?' MEASURED counters of those 8 h: "
               "TSK-0135 builder Fable ~950 k, merge rework Fable ~50 k, merge verify Opus ~270 k, TSK-0134 Opus ~344 k, "
               "half check Opus ~216 k, goal round Opus running, plus the lead's own Fable session with a long context "
               "on every step; Fable is weighted heavier in the plan. The generation-6 numbers say 'cheaper than "
               "generation 5 per goal' (937 k vs 630-896 k per stream + 2-4 verifier rounds + merge), not 'cheap'. "
               "DEC-0088 (1) had put a goal-sized build on the TOP rung; DEC-0087 (7) left the builder's default tier "
               "to the FR-0089 experiment -- the user decides it now, on cost, before the experiment.",
    "decision": "(1) BUILDER DEFAULT = OPUS at effort high: the `build` class of every kit ladder starts on opus (not on "
                "the role's worker pin, not on top); the harness-implementer of this repo pins opus. (2) ORCHESTRATOR "
                "= OPUS: the kits' project-manager / office-manager / research-lead pins go to opus and the `planning` "
                "class to opus -- the long-lived session is the biggest single consumer and orchestration is reading, "
                "not judgment-heavy generation; this repo's harness-lead pins opus from the next session. (3) VERIFIER "
                "= OPUS (unchanged); independence comes from the separate context and the adversarial order, not from a "
                "different model family (FR-0089 research B). (4) WHEN FABLE -- exactly two occasions, both bounded: "
                "(a) the ARCHITECTURE step of a LARGE goal (the `architecture` class stays `top`: one call, a document "
                "as output, the freeze the build falls from -- DEC-0034 rule 1); (b) ESCALATION: a build order that "
                "FAILED on opus climbs to fable by the ladder (DEC-0034 rule 2, already built) -- Fable is reached by "
                "a measured failure, never chosen up front; a PM may ask `rung: fable` on an order only with the reason "
                "on the order, and the checkpoint shows it. (5) 'GUT ORCHESTRIERT UND UEBERWACHT': what makes an Opus "
                "builder finish is not a stronger model but the form -- the whole goal on the lease, the fact-based "
                "checkpoint, the mid-goal check for LARGE goals, the goal round per AC, the escalation on FAIL, and the "
                "lead's Vorgefunden-resume after any interruption; the (g) table records rounds-to-PASS per rung so the "
                "default is re-measured, not believed. (6) COST DISCIPLINE ADDED to DEC-0088: agents read end lines and "
                "named sections, never whole run logs; reports to the lead are short; the lead restarts its own session "
                "with the handover prompt after each commit (the long context is a consumer); no experiment arm and no "
                "new agent without the user's word while the weekly budget stands above 50 %% spent. (7) The FR-0089 "
                "experiment stays: it now measures Opus-kit against Fable-alone -- the question the user actually has.",
    "consequences": "The top model is bought where judgment is concentrated (architecture, escalation) and nowhere as a "
                    "running cost; the office kit is unchanged (its top is opus already). Cost: an Opus builder may need "
                    "the escalation more often -- that is measured per rung in the (g) table. Rejected: Fable as builder "
                    "default (DEC-0088 (1)); a Fable verifier (cost without measured gain); asking the user per goal.",
    "work": ["PR-0011"],
    "source": "user messages 2026-09-11 ~07:00 and ~07:10; the agents' own token counters of 2026-09-10 23:00 - 2026-09-11 "
              "07:00 (round log generation-6-streams.md); DEC-0087 (7); DEC-0088; DEC-0091; DEC-0034; FR-0089 research B; "
              "team-kits/dev-team/ladder.yaml (classes planning/architecture: top, build: pin)",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
