"""Capture the user decision of 2026-09-06 on FR-0033 / PR-0009 AC-1: correspondence as a TEACHABLE
WORKFLOW (script + plain-language procedure the office-manager runs), not a role. Body on stdin to
`kernel.cli capture DEC`. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Schriftverkehr im Buero-Kit entschieden: ein beigebrachter Arbeitsablauf (Skript + Klartext-"
             "Anleitung, vom Buero-Manager ausgefuehrt und geprueft), keine eigene Rolle -- FR-0033 / PR-0009 AC-1",
    "context": "USER DECISION 2026-09-06 on the DEC-first proposal of stream G5-3 (TSK-0132, "
               "staging/TSK-0132/dec-correspondence.json). Two options with measured cost: (A) a teachable "
               "workflow -- scripts/letter_draft.py renders offer, reminder and customer letter from ledger + "
               "master data + business profile into outbox/, correspondence.yaml carries the user's terms "
               "(dunning levels, offer validity, closing lines), a reference skill correspondence/SKILL.md, "
               "the office-manager reviews every draft with the kit's plain-language procedure before it "
               "reaches the user -- 4 new files, 3 touched, no dispatch, no lease, no extra rung (DEC-0078 "
               "pins the office-manager at opus; the humanizer's reference_for already reaches the drafts); "
               "(B) a role -- one more specialist dispatched per letter, 11 files plus a ladder seam owned by "
               "G5-2, a second run reading each letter, a dispatch cycle per letter. The stream recommended "
               "(A) with FR-0033's own line ('measure what the PROC mechanism can already carry before "
               "adding a role'), FR-0028 (teach-once) and DEC-0056 (no scaffold larger than the house); a "
               "hybrid (reminders by the bookkeeper, letters by the manager) was rejected as two procedure "
               "texts for one capability. The user chose (A). The choice is not a one-way door: everything "
               "built for the workflow becomes a later role's procedure unchanged.",
    "decision": "(1) Correspondence is a teachable workflow of the office-manager: letter_draft.py + "
                "correspondence.yaml + the reference skill; the manager runs it, reviews the draft with the "
                "kit's procedure, and hands the user the letter to send. (2) No correspondence role, no "
                "preset entry, no model/effort map entry, no ladder seam -- the role wiring named in the "
                "proposal's 'NOT built until the answer' stays unbuilt. (3) What the workflow does not give "
                "and the texts must say: no second run reads a letter before it leaves (the user is the "
                "second reader); no parallel production of many letters. (4) The seven findings of "
                "verify-round-1 on the decision-neutral core (B1-B7) are closed in the same stream under "
                "this decision; a later role, if the user ever wants one, inherits the workflow as its "
                "procedure.",
    "consequences": "The office kit writes outward at the price of one script run and one review pass per "
                    "letter; the manager's own review is the only reading before the user. Rejected: the "
                    "role (a dispatch cycle per letter and a specialist for a volume-over-depth job); the "
                    "hybrid (two owners for one capability).",
    "source": "staging/TSK-0132/dec-correspondence.json; user answer 2026-09-06 'Beigebrachter Arbeitsablauf'; "
              "FR-0033; PR-0009; DEC-0056; DEC-0078; FR-0028; staging/TSK-0132/verify-round-1.md",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
