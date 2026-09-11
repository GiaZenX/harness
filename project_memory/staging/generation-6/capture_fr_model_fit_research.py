"""Capture the user's research wish of 2026-09-11 ~09:00: which model (sonnet / opus / fable) fits which task
scope, per Anthropic's own guidance and per user reports -- three short Sonnet researchers, then a synthesis that
feeds the tier rules (DEC-0095/0096). Body on stdin to `kernel.cli capture FR`. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "FR"]

BODY = {
    "title": "Recherche: welches Modell (Sonnet / Opus / Fable) fuer welchen Aufgabenumfang -- was Anthropic selbst "
             "und was Nutzer berichten -- als Grundlage fuer die Stufenregeln (DEC-0095/0096) statt Gefuehl",
    "request_text": "User 2026-09-11: 'Fable kuenftig als Umsetzer nur einmal kurz am Anfang beim Aufsetzen des "
                    "komplexen Plans der Hauptarchitektur und des Designs, und dann lediglich als letzte "
                    "Eskalationsstufe? Der Hook bremst den PM und fragt: Fable/Sonnet/Opus wirklich noetig/ausreichend. "
                    "Waere eine kurze Sonnet-Recherche sinnvoll, was User und Anthropic berichten, fuer welchen Umfang "
                    "und welche Tasks welches Modell am besten geeignet ist? Opus ist eigentlich sehr gut; Fable hat das "
                    "kleine Etwas, ist autonomer, versteht Zusammenhaenge besser, prueft sich selbst, ist kritischer -- "
                    "aber Opus macht fast die gleiche Arbeit deutlich guenstiger. Fable lohnt sich wohl nur als "
                    "Eskalationsstufe fuer sehr komplexe Analysen ueber viele Dateien / das ganze Repo / den ganzen Plan. "
                    "Sonnet nur fuer ganz kleine Sachen -- gut, aber manchmal etwas daemlich. Das ist mein Gefuehl, ich "
                    "kann mich taeuschen: drei oder vier Sonnet-Subagents als Recherche.'",
    "problem": "DEC-0095 (builder default opus) and DEC-0096 (effort before rung) were decided on the cost signal of "
               "one session (30 % of the weekly budget in 8 h) and on the user's impression; the FR-0089 research "
               "measured multi-agent vs single agent, not model-per-task-scope. The kits' ladders now encode "
               "architecture on the top rung, build on opus, escalation by failure -- a rule set that should rest on "
               "what the vendor documents (model selection guidance, effort docs, pricing, context/long-horizon "
               "claims) and on what practitioners measure (task size, file count, autonomy, self-checking), not on "
               "one repo's feeling.",
    "goal": "(1) Three short Sonnet research reports under staging/FR-0091/: A = Anthropic's own guidance (model "
            "overview, 'choosing a model', effort docs, pricing, agent/long-horizon notes, dated URLs); B = user and "
            "practitioner reports 2026 on Opus vs Fable vs Sonnet for coding by scope (small edits, multi-file "
            "features, repo-wide analysis, architecture/design, self-verification, autonomy), with sources; C = "
            "published benchmarks and cost-per-task-class comparisons where they exist (SWE-bench-style, agentic "
            "coding, long-context), with the honest limit that benchmarks are not our tasks. (2) The lead's "
            "synthesis: a table task-class -> rung + effort, checked against DEC-0095/0096 -- what they confirm, what "
            "they would change, what only our own (g) tables can settle. (3) A DEC if the synthesis changes a rule; "
            "otherwise the confirmation recorded on DEC-0095.",
    "source": "user message 2026-09-11 ~09:00; DEC-0095; DEC-0096; DEC-0091; DEC-0092 (the checkpoint question); "
              "FR-0089 + staging/FR-0089/*.md; the (g) tables of generations 5 and 6",
    "related_pr": "PR-0011",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
