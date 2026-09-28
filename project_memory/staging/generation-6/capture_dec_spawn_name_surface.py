"""Lead decision 2026-09-27 on stream B's hand-over: FR-0092's spawn name needs `description` in the closed set of
spawn/lease surface fields DEC-0092 (1) fixed. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "FR-0092 praezisiert DEC-0092 (1): der sichtbare Spawn-Name (`description`, vom Dispatch-Kopf als "
             "`spawn_description` vorgegeben) gehoert zur geschlossenen Menge der Spawn-/Lease-Felder -- ein NAME, "
             "kein Begruendungsfeld",
    "context": "Stream B of order 7 (TSK-0154) built FR-0092 (the user's explicit wish 2026-09-11: every started "
               "agent's visible name carries role + model + effort + stream letter) and handed one line to the merge: "
               "tools/test_light_kit.py::test_no_spawn_or_lease_surface... holds DEC-0092 (1)'s CLOSED set of surface "
               "fields, and `description` / `spawn_description` are not in it. DEC-0092 (1) closed the set to keep a "
               "free-text REASONING field off the lease (the fact checkpoint replaced it).",
    "decision": "(1) `spawn_description` (the exact string the dispatch header hands the PM) and the spawn payload's "
                "`description` join the closed set; the set stays closed for everything else. (2) What makes this "
                "consistent with DEC-0092 (1): the value is DERIVED by the kernel (role, rung, effort, stream letter), "
                "never typed as prose by the PM, and the gate compares it character for character -- it carries no "
                "judgement. (3) The merge of order 7 applies the test change with this DEC's id in its docstring.",
    "consequences": "The user sees in every agent list which role, model, effort and stream runs. Rejected: keeping the "
                    "name out of the set (FR-0092 would be unbuildable on the running path).",
    "work": ["PR-0012"],
    "source": "project_memory/staging/TSK-0154/protocol.md (hand-over list); FR-0092; DEC-0092 (1)",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
