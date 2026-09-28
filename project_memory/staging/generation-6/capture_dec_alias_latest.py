"""User 2026-09-28 ~21:4x on Sonnet 5.5: keep the unversioned aliases (latest model), measure what each model is good
for, the PM picks the combination. Resolves DEC-0114 vs DEC-0124. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Modell-Aliase bleiben ohne Versionsnummer (immer das neueste Modell einer Familie); gemessen wird, WOFUER "
             "ein Modell taugt, und der PM waehlt die Kombination -- der Messbeleg aus DEC-0124 gilt fuer den Wechsel "
             "einer Klasse auf eine andere Modellfamilie, nicht fuer ein Versionsupdate hinter demselben Alias",
    "context": "Sonnet 5.5 released 2026-09-28 (claude-watcher radar/2026-09-28-claude-by-claude.md): the Kilo class "
               "names only `sonnet`, which Claude Code >= 2.1.284 resolves to Sonnet 5.5 -- DEC-0114 (user 2026-09-25: "
               "automatic) and DEC-0124 (plan V2.5: a new model replaces a ladder model only with measured proof) "
               "collided for the first time. The lead asked; the user answered: 'Dachte Standard ist Opus? Aber ja "
               "auf jeden Fall updaten. Bzw. wird eh das aktuellste genommen, da wir keine Versionsnummer mitgeben. "
               "Bloss hier muss man auch immer messen wofuer es gut ist, der PM soll ja intelligent die Kombination "
               "aussuchen.'",
    "decision": "(1) The kits keep unversioned aliases (opus, sonnet; the Codex equivalents) -- a new version behind an "
                "alias arrives automatically. (2) DEC-0124's 'measured proof' applies when a model CLASS moves to "
                "another family or model (e.g. Kilo from Sonnet to Opus-low), not to a version update behind the same "
                "alias. (3) Every new model/version gets a MEASUREMENT of what it is good for (fixed repo tasks with "
                "tests, solved / tokens / cost per solved task / verification rounds, actual model read from the "
                "transcript), and the result goes into the 'which model and effort for what' guide the PM reads; the "
                "PM chooses model class x effort per order from that guide (stream C). (4) Dev/research builders stay "
                "on Opus by default; Kilo (Sonnet) only for mechanical work with a test acceptance (DEC-0097/0112); "
                "the office kit's Sonnet default is part of the first measurement.",
    "consequences": "Sonnet 5.5 is live wherever Claude Code updated; the watchers' model question becomes 'what is it "
                    "good for' plus a measurement order, not 'swap yes/no'. Stream C builds the guide file and the "
                    "measurement harness.",
    "work": ["PR-0012"],
    "source": "user answer 2026-09-28 (AskUserQuestion); radar/2026-09-28-claude-by-claude.md; DEC-0114; DEC-0124",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
