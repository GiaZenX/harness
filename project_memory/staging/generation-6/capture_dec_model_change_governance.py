"""User 2026-09-28 ~22:1x: the class/effort mapping changes only with him, only on a new model, always measured.
Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Die Modell-Zuordnung (Klasse x Effort je Rolle) aendert sich nur in Abstimmung mit dem Nutzer, nur wenn "
             "ein neues Modell erscheint, und immer nach einer gezielten Messung auf einem festen Pruefstand; das "
             "Kosten-Nutzen-Verhaeltnis entscheidet, nicht der Name",
    "context": "User 2026-09-28: 'Wenn in der Recherche irgendwann ergibt dass Fable guenstiger wird und besser als "
               "Opus kann man damit dynamischer umgehen. Aber momentan eben nicht als Standard ... Das hat auch viel "
               "mit Kosten Nutzen zu tun. Wenn irgendwann mal das beste Modell richtig guenstig ist, dann kann man es "
               "fuer alles nutzen. Oder wenn das kleinste Modell irgendwann so gut ist wie das beste dann auch. Aber "
               "momentan wuerde ich es so belassen. Das aendern wir nur in Abstimmung und nur wenn neue Modelle "
               "rauskommen und wir muessen sie immer messen. Am besten mit gezielten Tests.'",
    "decision": "(1) The mapping of DEC-0127/0129/0130 stands as the current default. (2) It changes ONLY when a new "
                "model or version appears (reported by the watchers) AND a measurement on the fixed test bench shows "
                "a better cost-benefit AND the user agrees on a card that shows the numbers. (3) THE TEST BENCH "
                "(built in wave-1 stream C): per class a fixed set of real tasks from this repo's history, each with "
                "a test that is red before and green after (plus a quote-checked summary set for Kilo); every "
                "candidate runs each task at least 3 times at the efforts in question; scored: solved, verification "
                "rounds, tokens, wall time, cost per SOLVED task, the actual model/effort read from the transcript. "
                "(4) Direction is open both ways: the best model for everything if it becomes cheap enough, the "
                "smallest if it becomes good enough -- the bench decides, the user approves. (5) The watchers' "
                "new-model question triggers a bench run instead of a recommendation.",
    "consequences": "No silent re-mapping; a new model costs one bench run and one user card. The bench needs task "
                    "selection from archived TSKs with red/green tests and an SDK-driven runner.",
    "work": ["PR-0012"],
    "source": "user message 2026-09-28; DEC-0126; DEC-0127; DEC-0128; DEC-0129; DEC-0130; FR-0098 section 3",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
