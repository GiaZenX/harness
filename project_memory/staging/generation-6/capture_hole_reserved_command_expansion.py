"""TSK-0158 verify round 2 residue (2026-09-27 ~21:20): the door WORD itself produced by a shell expansion is not
seen by `_reserved_command`. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"]
env = dict(os.environ, PYTHONPATH="team-kits")

HOLE = {
    "title": "Regel-4-Leser: kommt das Befehlswort selbst (upkeep, dispatch, ...) erst aus einer Shell-Erweiterung "
             "oder einer PowerShell-Array-Uebergabe, erkennt das Gate keinen reservierten Befehl und laesst durch",
    "related_pr": "PR-0012",
    "observed": "MECHANISM: team-kits/{dev,office,research}-team/hooks/gate_write_scope.py `_reserved_command` (from "
                "~:1238) reads the first positional from the GATE's words. When the shell produces the subcommand "
                "word itself (an expansion at that position, or PowerShell splatting the whole argv as an array), "
                "the gate sees no reserved command and `_upkeep_refusal` answers ''. Not H227 (no shifted role "
                "position) and not L43 (which names sh -c / bash -c / eval wrappers). MEASURED CHAIN (TSK-0158 "
                "verify round 1, log C:/Offline Repos/v2-testbed/_round-scratch/TSK-0158-verify/logs-n1.txt; "
                "reported in round 2): one bash and one PowerShell form, gate rc 0, the kernel's parser on the "
                "real shell's argv reads cmd=upkeep action=prune-memory role=database-engineer. REACH: "
                "`_reserved_command` is the one reader for every rule-4 class, so dispatch / install-type commands "
                "are likely reached too (read, not measured). Present since rule 4, not introduced by TSK-0158. "
                "VERDICT: open; closing belongs to wave 1 stream B of plan V2.5 (kernel write log + after-check, no "
                "command-line guessing), same as H227.",
    "expected": "No command-line spelling lets a subagent run a reserved kernel door; enforced where the kernel acts.",
    "repro": "See the verifier's rig under _round-scratch/TSK-0158-verify/ (spellings kept there).",
    "severity": "medium",
    "acceptance_criteria": [
        {"id": "AC-1", "text": "the measured bash and PowerShell forms no longer reach a reserved door from a subagent "
                               "-- a test naming this bug, red on 2026.09.27-9"},
    ],
    "source": "TSK-0158 verify round 2 (staging/TSK-0158/verify-round-2.md)",
    "limits": "Offen bis Welle 1 Strom B. Begrenzt: ein Subagent braucht eine absichtlich verdrehte Schreibweise; "
              "betroffen sind Kernel-Tueren (Aufraeumen, Bestellen), nicht die Projektakte selbst, die weiter nur "
              "der Kernel schreibt; alles liegt im Git-Verlauf.",
}

r = subprocess.run(BASE + ["capture", "BUG", "--hole"], cwd=ROOT, env=env, input=json.dumps(HOLE),
                   capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
if r.returncode:
    sys.exit(r.returncode)
r = subprocess.run(BASE + ["migrate-holes", "--reindex"], cwd=ROOT, env=env, capture_output=True, text=True,
                   encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
