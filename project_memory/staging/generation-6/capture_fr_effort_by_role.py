"""User 2026-09-28 ~21:0x: effort per role (PM/architect/designer high-effort spec, workers medium) -- research wish.
Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "FR"]

BODY = {
    "title": "Recherche: welche Denktiefe (effort) fuer welche Rolle -- Planer (PM/Architekt/Designer) hoch fuer die "
             "Festlegung der Details, Bauer eher mittel, Pruefer hoch? Grundlage fuer Strom C (zwei Achsen)",
    "request_text": "User 2026-09-28: 'Haben wir mittlerweile definiert welchen effort fuer was zu nutzen ist? Hab ein "
                    "interessantes Video gesehen. Scheint so als waere wichtig dass der PM/Architekt/Designer eher auf "
                    "xhigh laeuft um Details festzulegen und die worker eher auf Medium zu halten. Kannst ja eine "
                    "Recherche hierzu starten.' The video (YouTube short @DIYSmartCode 'The Truth About Claude Code "
                    "Effort Levels', AI-generated, screenshots in the session) claims: same prompt on Opus 5.5 at "
                    "low/medium/high/max took 1.5/4/11/39 min; with an interview->spec step the results became much "
                    "more alike; on 370 attempts Fable 5.1 low vs max: passed 140->214, missed cases fell, but 'picked "
                    "the wrong reading' ROSE 25->47 and tokens tripled (73k->222k median); max catches missed cases "
                    "but will not fix a wrong approach; rule of thumb low=sketch, medium=feature, high=bug/edge cases, "
                    "max=hard end-to-end hand-off; 'build low/med, review yourself, verify high'.",
    "source": "user message 2026-09-28 with 9 screenshots; plan V2.5 section 4 (Welle 0 block, research 0c: xhigh "
              "scored worse than high in arXiv 2608.01347); DEC-0088 (4); DEC-0118",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
