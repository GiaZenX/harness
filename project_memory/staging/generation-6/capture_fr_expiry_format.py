"""Capture P6 of the TSK-0135 goal round as a wish: the expiry in the German approval question is a machine
timestamp (2026-09-25T05:06:25Z); a fixed, German-readable UTC date form would be equally deterministic. Deferred by
the rework under DEC-0095 (6) (kernel file -> kit hash -> stamp -> the character-comparing suites); verify round 2
asked for the item so the deferral survives the staging file. Body on stdin to `kernel.cli capture FR`."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "FR"]

BODY = {
    "title": "Das Ablaufdatum in der deutschen Freigabe-Frage lesbar machen: '25.09.2026, 05:06 UTC' statt "
             "'2026-09-25T05:06:25Z' -- gleich deterministisch, aber die Zeile, die der Nicht-Entwickler beurteilt, "
             "liest sich nicht mehr wie eine Maschine",
    "request_text": "Verifier finding P6 of the TSK-0135 goal round (2026-09-11, verify-goal.md): kernel/approvals.py "
                    ":1601-1605 renders the routine approval's expiry as an ISO timestamp with Z inside the German "
                    "question built for AC-7 of PR-0011; determinism is required (gate_approval compares character "
                    "for character in another process) but a fixed date format is equally deterministic; the value "
                    "also sits up to two hours beside the user's clock (UTC vs local) without saying so.",
    "problem": "The one surface where the user's reading is the safeguard (BUG-0073, BUG-0271) still carries a "
               "machine-shaped value after the German rewrite; the rework of 2026-09-11 deferred the fix under "
               "DEC-0095 (6) because approvals.py is a kit-hash input: the change costs a stamp and re-runs of the "
               "character-comparing suites, the wrong price for a label while the weekly budget stands where it does.",
    "goal": "build_question renders the expiry (and any other timestamp a user must judge) as a fixed, "
            "German-readable UTC form with the zone named; the gate's comparison and the hash stay deterministic; "
            "a test renders every kind that carries an expiry and refuses an ISO 'T' / 'Z' shape in the question or "
            "option text; carried by the next order that touches kernel/approvals.py anyway (one stamp).",
    "source": "project_memory/staging/TSK-0135/verify-goal.md (P6); verify-goal-2.md (item 6); protocol.md section 6 (8); "
              "DEC-0095 (6); BUG-0271; BUG-0073",
    "related_pr": "PR-0011",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
