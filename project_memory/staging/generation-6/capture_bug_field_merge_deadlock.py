"""Field report from synaipse-unified (relayed by the user 2026-09-28 ~00:xx): merge/verification deadlock for a goal
built in parallel branches. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "BUG"]

BODY = {
    "title": "Feld: Sperre im Kreis -- die Schutzregel verlangt eine bestandene Pruefung des zusammengefuehrten "
             "Stands, verbietet aber das Zusammenfuehren paralleler Arbeitszweige desselben Ziels vor dieser "
             "Pruefung (synaipse P2/P3 stehen)",
    "related_pr": "PR-0012",
    "observed": "REPORTED by the synaipse-unified PM, relayed by the user 2026-09-28: 'Die Schutzregel verlangt eine "
                "bestandene Pruefung des zusammengefuehrten Stands, verbietet aber gleichzeitig das Zusammenfuehren "
                "paralleler Arbeitszweige ... Die Pruefung braucht genau diesen zusammengefuehrten Stand. Dadurch "
                "stehen P3 und die naechsten P2-Schritte.' The PM refuses a rebase/cherry-pick workaround and "
                "proposes one branch per goal until a kit fix. Forensics (rule source, session, repo) pending.",
    "expected": "A goal built in parallel branches has a legal path to one verified merged state (e.g. an "
                "integration branch the verification runs on, or merge-then-verify with the gate reading the "
                "verification of the merged digest) -- no circular refusal.",
    "repro": "Pending forensics: staging/BUG-field-merge-deadlock (see the lead's round log).",
    "severity": "high",
    "acceptance_criteria": [
        {"id": "AC-1", "text": "a goal with two parallel branches reaches a verified merged state through the kit's "
                               "own path -- a test naming this bug, red on 2026.09.27-9"},
    ],
    "source": "synaipse-unified PM message relayed by the user 2026-09-28",
    "limits": "Im Feld blockiert: P3 und die naechsten P2-Schritte in synaipse stehen. Begrenzt: ein Arbeitszweig "
              "pro Ziel umgeht die Sperre ohne Regelbruch, kostet aber Parallelitaet.",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
