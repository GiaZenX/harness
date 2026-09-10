"""Capture the user's question of 2026-09-06 as a wish: is the multi-agent harness worth its cost against a
single top-tier agent (Fable) for real product work -- measured, not felt. Research first (three Sonnet
researchers), then a controlled experiment. Body on stdin to `kernel.cli capture FR`. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "FR"]

BODY = {
    "title": "Kosten / Nutzen / Qualitaet / Effizienz des Multi-Agenten-Harness gegen EINEN Fable-Agenten -- "
             "Recherche (was die Welt gemessen hat) und ein kontrolliertes Experiment (dieselbe Aufgabe, zwei Wege), "
             "bevor die naechste Produkt-Generation den Schnitt waehlt",
    "request_text": "User 2026-09-06: 'wir bauen hier ein riesen Multi Agenten System aber ich stelle folgendes in "
                    "Frage: Kosten Nutzen Qualitaet Effizienz Faktor. Wenn ich spaeter ein Produkt/Projekt bauen "
                    "lasse habe ich das Gefuehl dass ein einzelner Fable schneller, effizienter und guenstiger ist "
                    "und die Qualitaet hoeher ist. Wenn man mit Fable orchestriert und Sonnets zur Ausfuehrung "
                    "laesst und ihnen viel Spielraum laesst, coden sie nicht so gut, haben nicht so viel und gute "
                    "Ideen und drehen viele Runden. Ich sehe es oft bei Frontend: sage ich Fable genau das gleiche "
                    "wie dem Multi-Agenten-System, braucht das System laenger, das Ergebnis ist meist schlechter "
                    "und kostet mehr. Mit GPT (Astra) macht er ewig rum, Tokens sofort weg, kaum Fortschritt. Was "
                    "steht im Internet dazu? Sind wir zu gross oder zu kompliziert geworden?'",
    "problem": "The harness's own measurements point the same way for some work: generation 4 cost ~4 M "
               "implementer + ~5.6 M verifier tokens over five agents and 3-5 verification rounds per stream; "
               "generation 5 so far ~2.5 M per stream with the same round counts; a large share of findings "
               "were prose-vs-code and coordination (seams, re-cuts, the lead's own ordering errors), not "
               "product defects. The user's frontend comparison (same brief to one Fable vs the pipeline: the "
               "pipeline slower, worse, dearer) is an observation without a measurement in this repo. Nobody "
               "has run the controlled experiment: same task, same brief, (a) one Fable end to end, (b) the "
               "kit's pipeline, compared on wall-clock, tokens, and a quality judgment the user can make.",
    "goal": "(1) Research: what the field has measured about multi-agent vs single strong agent (cost "
            "multipliers, error compounding, failure taxonomies, when orchestration wins -- breadth, "
            "independent verification, parallel independent work -- and when it loses -- sequential creative "
            "work, design coherence, under-specified worker orders), with sources; (2) an experiment item: one "
            "frontend task the user can judge, run both ways with the same brief, measured on tokens, "
            "wall-clock, rounds and the user's quality verdict; (3) a decision on the kits' default: the "
            "smallest team by default (solo Fable for creative / frontend / small projects), the pipeline "
            "where independent verification or parallel breadth is worth its price, workers with narrow "
            "testable slices instead of 'Spielraum'.",
    "source": "user message 2026-09-06; the (g) tables of generation 3 (staging/TSK-0120/merge-protocol.md section 9), "
              "generation 4 (staging/TSK-0126/merge-protocol.md section 9, DEC-0080) and generation 5 (staging/"
              "generation-5-streams.md); DEC-0063 (tiers), DEC-0081 (streams Opus, merge Fable), DEC-0034/0077 (ladders)",
    "related_pr": "PR-0003",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
