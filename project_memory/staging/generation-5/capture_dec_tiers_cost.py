"""Capture the user's tier correction of 2026-09-05 (minutes after the generation-5 spawn): streams on
Opus, only the MERGE round on Fable -- cost. Amends DEC-0077 (4) and DEC-0080 (8). Body on stdin to
`kernel.cli capture DEC`. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Stufen korrigiert: die Stroeme einer Generation laufen auf Opus (high), nur die MERGE-Runde "
             "auf Fable (high; xhigh sobald der Spawn es erreicht) -- Kostenentscheidung des Nutzers, ersetzt "
             "DEC-0077 (4) und DEC-0080 (8)",
    "context": "USER DECISION 2026-09-05, minutes after the three generation-5 streams were spawned on Fable "
               "5.1: 'ich glaube wir sollten nur fuer den Merge auf fable hochstufen, die einzelnen Stroeme "
               "auf opus. Es ist sonst zu teuer'. DEC-0077 (4) / DEC-0080 (8) had set implementers to Fable "
               "(G5-2/G5-3 xhigh, G5-1 high) with verifiers on Opus, as a measured re-run of the DEC-0063 "
               "prose-overclaim finding on Fable 5.0. Measured facts behind the cost: generation 4 used ~4 M "
               "implementer and ~5.6 M verifier tokens over five agents; Fable's headline price is the top "
               "tier; the spawn surface has no effort parameter, so xhigh was not reachable anyway (all three "
               "streams ran on high). The lead stopped the three Fable agents within minutes of the spawn "
               "and respawned the SAME items (TSK-0130/0131/0132) on Opus; whatever the Fable agents wrote "
               "to disk is read by their successors ('Vorgefunden').",
    "decision": "(1) Stream implementers run on Opus at effort high; stream verifiers on Opus at effort high "
                "(unchanged). (2) The MERGE round's implementer runs on Fable (high today; xhigh once G5-1 "
                "delivers an effort-selectable implementer definition under DEC-0077), because the merge is "
                "where generation 4 paid the most rounds (four) and where the reach of every stream meets. "
                "(3) A design pass (taste, DEC-0063) stays Fable. (4) The (g) table of generation 5 still "
                "measures the claim class per tier -- now Opus streams vs the Fable merge -- and the "
                "generation-5 retrospective decides whether the merge tier earned its price. (5) DEC-0076 "
                "(rungs), DEC-0077 (1)-(3) (two axes, escalation built) and DEC-0078 (per-kit ladders) are "
                "untouched: this decision is about THIS repo's own three roles, not the kits' ladders.",
    "consequences": "Generation 5 costs roughly what generation 4 did per stream; the one place with the "
                    "Fable premium is the merge. Cost of the switch itself: three spawns and a few minutes "
                    "of Fable work discarded (measured small: the agents were in their reading phase). "
                    "Rejected: keeping the Fable streams (the user's cost line); Opus for the merge too "
                    "(the merge is the round with the highest rework count and the widest reach).",
    "source": "user message 2026-09-05; DEC-0077; DEC-0080; DEC-0063; project_memory/staging/generation-5-streams.md",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
