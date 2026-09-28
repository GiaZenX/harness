"""TSK-0156 verify round 1, finding F4 (2026-09-27 16:5x): a sweep strands CHILD_WAITING. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "BUG"]

BODY = {
    "title": "Ein Kind wartet auf seinen eigenen Hintergrundlauf; fegt die Leitung dann seine Lease, bleibt "
             "CHILD_WAITING fuer immer am Task stehen und dispatch schickt die Leitung in ein Warten ohne Ende",
    "related_pr": "PR-0012",
    "observed": "MEASURED by the TSK-0156 verifier (staging/TSK-0156/verify-round-1.md F4) with real gate_dispatch "
                "processes on the merged tree (order 7, stream B): child waits on its own background run -> lead "
                "runs `sweep-leases` (the kernel itself sends it there) -> resume: 'bound task: None'; child write "
                "rc 2; last Stop 'ended: None | waiting: ...'; lead Stop rc 0 with no finding; `dispatch` rc 1 "
                "'resumes when that run completes ... wait for its result' although the run finished and the child "
                "ended. `transition ... FAILED` works (rc 0) but that branch does not name it. Sites: "
                "team-kits/kernel/dispatch.py:1886, :2225, :2289, :1798.",
    "expected": "sweep_expired_leases leaves the lease of a task in CHILD_WAITING standing (or clears the waiting "
                "mark with it, consistently), and the WAITING branch of dispatch names the FAILED way out.",
    "repro": "See verify-round-1.md F4: the chain child-wait -> sweep-leases -> resume -> dispatch.",
    "severity": "medium",
    "acceptance_criteria": [
        {"id": "AC-1", "text": "the chain wait -> sweep -> resume/dispatch no longer strands the task: a test naming "
                               "this bug, red before the fix in a copy outside the repo"},
        {"id": "AC-2", "text": "the WAITING branch's refusal names the `transition ... FAILED` way out"},
    ],
    "source": "project_memory/staging/TSK-0156/verify-round-1.md (F4)",
    "limits": "Kein Datenverlust; ein Auftrag bleibt haengen, bis jemand ihn von Hand auf FAILED setzt.",
}

env = dict(os.environ, PYTHONPATH="team-kits")
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
