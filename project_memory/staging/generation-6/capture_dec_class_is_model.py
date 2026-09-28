"""User correction 2026-09-28: the CLASS is the model alone (size tier), effort is a separate axis. Corrects DEC-0128's
naming. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Modellklasse = nur das Modell (Groessenstufe), unabhaengig vom Effort: Milli < Kilo (Haiku) < Mega "
             "(Sonnet) < Giga (Opus) < Tera (Fable) < Peta; Effort ist eine eigene Achse; Anbieter mit weniger "
             "Modellen werden ehrlich eingestuft",
    "context": "User 2026-09-28, correcting the lead (who had mixed model and effort into the classes, DEC-0128 "
               "wording 'Giga = Opus xhigh'): 'Klasse ist nur das Modell unabhaengig vom effort. Effort ist separat. "
               "Hat ein Anbieter nur ein Modell oder weniger Modelle, ist es ehrlich einzustufen. Haiku ist Kilo, "
               "Sonnet Mega, Opus Giga, Fable Tera. Wenn was kleineres als Haiku rauskommt, dann ist es Milli. Wenn "
               "was groesseres als Fable rauskommt, dann Peta. Effort-Stufen aendern ja nur die Denktiefe und wir "
               "muessen da trennen.'",
    "decision": "(1) MODEL CLASS names a model's size/capability tier and nothing else: Milli (below Haiku) < Kilo = "
                "Haiku < Mega = Sonnet < Giga = Opus < Tera = Fable < Peta (above Fable). (2) EFFORT (low / medium / "
                "high / xhigh / max) is the second, independent axis; an order carries class AND effort, each with its "
                "reason (DEC-0124, DEC-0127 for the effort per role). (3) Other providers' models are placed on the "
                "SAME scale by honest capability (measured where possible), not forced to fill every rung -- a provider "
                "with fewer models simply leaves rungs empty. (4) Usage rules stay separate from the names: Kilo "
                "(Haiku) never writes code and opens for read-only routine work only after the measurement of DEC-0128 "
                "(3); Tera (Fable) only for a named step with a measured advantage (DEC-0128 (2)); a version update "
                "behind an alias keeps its class (DEC-0126). (5) This supersedes the class wording of DEC-0128 (1)/(2) "
                "('Giga = Opus xhigh', 'Tera = Fable' as effort-bound) and the plan V2.5 section 4 sentence 'Kilo = "
                "Sonnet 5, Mega = Opus 5.5, Giga = Opus 5.5 (Fable capped)'.",
    "consequences": "The ladder files and the role variants name classes by model only; the task-to-class questions "
                    "(FR-0098) pick a CLASS, the effort rules (DEC-0127) pick an EFFORT. Default builder = Giga "
                    "(Opus) at medium; mechanical work with a deciding test = Mega (Sonnet); planning = Giga at xhigh.",
    "work": ["PR-0012"],
    "source": "user message 2026-09-28; DEC-0124; DEC-0126; DEC-0127; DEC-0128",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
