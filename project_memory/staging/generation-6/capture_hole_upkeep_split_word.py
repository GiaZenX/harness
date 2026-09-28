"""TSK-0158 verify round 1, finding A (2026-09-27 ~21:10): the upkeep bound's SUCCEEDING direction -- a word the
shell splits shifts the role position. File it as a hole and correct BUG-0327's verdict. Not idempotent."""
import json
import os
import subprocess
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"]
env = dict(os.environ, PYTHONPATH="team-kits")

HOLE = {
    "title": "upkeep-Schranke, gelingende Richtung: ein Wort, das die Shell in mehrere Argumente aufteilt, "
             "verschiebt die Rollenposition -- das Gate liest die eigene Rolle, der Kernel eine fremde",
    "related_pr": "PR-0012",
    "observed": "MECHANISM: team-kits/{dev,office,research}-team/hooks/gate_write_scope.py `_upkeep_refusal` "
                "parses the gate's word list with the kernel's parser; when that parse SUCCEEDS and names the "
                "caller's own role, the gate passes -- but the shell may expand one gate word into several argv "
                "words (bash expansions, PowerShell array arguments), so the kernel's parser reads ANOTHER role. "
                "Same class as TSK-0157's N1 (gate words != shell argv), the adding direction; present since the "
                "bound was built in TSK-0156, not new with rework 2. MEASURED CHAIN (TSK-0158 verify round 1, "
                "finding A; rig C:/Offline Repos/v2-testbed/_round-scratch/TSK-0158-verify/): bound "
                "backend-developer subagent, real dev-kit gate process rc 0, then a real shell with a stand-in "
                "scripts/harness.py whose argv the kernel's build_parser() reads: role=database-engineer -- four "
                "bash spellings and two PowerShell spellings, each gate rc 0. A subagent can prune ANOTHER role's "
                "craft memory (BUG-0325 in the other direction). The spellings stay in the rig, not here. "
                "Wrapper forms (function, xargs, bash -c, eval) are the separately named limit L43. VERDICT: open; "
                "not closable by another command-line reading (the lead's decision for this merge); the closing "
                "belongs to wave 1 stream B of plan V2.5 (kernel write log + after-check instead of command-line "
                "guessing).",
    "expected": "A subagent cannot make the kernel prune another role's memory by any spelling; enforced where "
                "the kernel acts (write log / caller identity), not by reading the command line.",
    "repro": "See the verifier's rig under _round-scratch/TSK-0158-verify/ (test_zz_verify_0158.py).",
    "severity": "medium",
    "acceptance_criteria": [
        {"id": "AC-1", "text": "the six measured spellings no longer reach another role's memory -- a test naming "
                               "this bug, red on 2026.09.27-8"},
    ],
    "source": "TSK-0158 verify round 1 (staging/TSK-0158/verify-round-1.md, finding A)",
    "limits": "Offen bis Welle 1 Strom B. Begrenzt: nur Handwerks-Notizen anderer Rollen betroffen, keine "
              "Projektakte und kein Code; die Notizen liegen im Git-Verlauf und sind wiederherstellbar.",
}

r = subprocess.run(BASE + ["capture", "BUG", "--hole"], cwd=ROOT, env=env, input=json.dumps(HOLE),
                   capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
if r.returncode:
    sys.exit(r.returncode)
new_id = r.stdout.split()[0]

with open(os.path.join(ROOT, "project_memory", "bugs", "active", "BUG-0327.yaml"), encoding="utf-8") as fh:
    observed = (yaml.safe_load(fh) or {})["observed"]
old = "VERDICT: over-refusal, no gap in the protection."
assert old in observed, "verdict sentence not found"
observed = observed.replace(
    old, "VERDICT: over-refusal in the FAILING direction. It is NOT 'no gap': the SUCCEEDING direction (a word "
         "the shell splits shifts the role position; gate rc 0, kernel reads another role) is open and filed as "
         "%s (TSK-0158 verify round 1, finding A)." % new_id)
r = subprocess.run(BASE + ["update", "BUG-0327"], cwd=ROOT, env=env, input=json.dumps({"observed": observed}),
                   capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
