"""Give H223-H226 their `limits` (what takes the place of the protection) -- test_gates
test_every_hole_states_a_verdict_and_an_unclosed_one_names_its_limit, 2026-09-28 11:24. Then reindex the hole list."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"]
env = dict(os.environ, PYTHONPATH="team-kits")

LIMITS = {
    "BUG-0325": "Die upkeep-Schranke aus TSK-0156 verweigert einem Subagenten die Tueren, die fremden oder "
                "gemeinsamen Zustand aendern; die zwei gemessenen Restrichtungen sind als H227/H228 benannt und "
                "vom Nutzer als Ausnahme bis Welle 1 Strom B angenommen. Geloeschte Notizen liegen im Git-Verlauf.",
    "BUG-0327": "Nur Ueber-Verweigerung: ein Subagent kann die Hilfe eines upkeep-Befehls nicht lesen; der Lead "
                "kann es, und keine Tuer oeffnet sich dadurch.",
    "BUG-0328": "Der Auftrag bleibt stehen, bis der Lead ihn auf seinen Ausweg-Status setzt; dispatch und "
                "sweep-leases nennen diesen Ausweg. Kein Datenverlust; das Kind schreibt ungebunden nichts (rc 2).",
    "BUG-0329": "Nur ein doppelter Anzeigename zweier Agenten; Leases, Auftrag und Dateibesitz bleiben getrennt "
                "(running_leases zaehlt beide).",
}

for item, text in LIMITS.items():
    r = subprocess.run(BASE + ["update", item], cwd=ROOT, env=env, input=json.dumps({"limits": text}),
                       capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr[-800:])
    if r.returncode:
        sys.exit(r.returncode)
r = subprocess.run(BASE + ["migrate-holes", "--reindex"], cwd=ROOT, env=env, capture_output=True, text=True,
                   encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
sys.exit(r.returncode)
