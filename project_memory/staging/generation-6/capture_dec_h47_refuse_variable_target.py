"""The user's answer to the H47 / BUG-0139 class question of TSK-0152 (protocol section 6), 2026-09-26. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "H47: Gate 1 dieses Repos lehnt eine Umleitung ab, deren Ziel eine Variable enthaelt -- es loest "
             "sie nicht auf (Richtung (c) der Klassenfrage aus TSK-0152)",
    "context": "TSK-0152 protocol section 6, MEASURED 2026-09-26 as gate-1 processes: `F=team-kits/kernel/state.py; "
               "echo x > $F` rc 0, `... > \"$F\"` rc 0, `F=project_memory/generated/index.yaml; echo x > $F` rc 0 "
               "for every caller (canonical state). Mechanism: `_harness._could_name_a_path` reads a word as a possible "
               "path only with a separator or in program position; a redirect TARGET is neither. The kits resolve such "
               "variables since TSK-0070. Asked with three options (shared reader / own copy / refuse), the user chose "
               "'Ablehnen' (the builder's and the lead's recommendation).",
    "decision": "(1) The redirect target of a write-capable stage is ALWAYS a path, so gate 1 of this repo refuses a "
                "redirect whose target carries a shell expansion (`$`, backtick, `$(`) instead of resolving it -- the "
                "same answer the gate already gives a word it cannot place. (2) No second copy of the kits' resolver, "
                "no change to the kits' shared reader. (3) Cost accepted: harmless lines like `echo x > $LOG` are "
                "refused; the remedy text says to spell the path. (4) Built as a patch site of the user's next patch "
                "(the gate is the user's file) with a test in .claude/hooks/test_gates.py naming BUG-0139, red before "
                "the patch and green after.",
    "consequences": "Closes the last measured path from a variable into canonical state at this repo's gate. Rejected: "
                    "(a) shared reader (changes what the kits allow in every project), (b) own copy (two versions of "
                    "one rule drift).",
    "work": ["PR-0012"],
    "source": "project_memory/staging/TSK-0152/protocol.md section 6; user answer 2026-09-26 ~16:3x; DEC-0070 rule 2",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr[-1500:])
sys.exit(result.returncode)
