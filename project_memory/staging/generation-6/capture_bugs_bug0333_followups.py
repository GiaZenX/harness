"""BUG-0333 forensics follow-ups (2026-09-28 ~10:3x): verdict masking + git history bypass hole. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
BASE = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "BUG"]
env = dict(os.environ, PYTHONPATH="team-kits")
SRC = "project_memory/staging/BUG-0333/forensics-2026-09-28.md"

MASK = {
    "title": "Ein bestandenes Pruefurteil ueber EINEN Auftrag ueberdeckt ein durchgefallenes Urteil ueber das "
             "ganze Ziel -- das Merge-/Liefer-Gate liest je Art nur das neueste Urteil, Auftrag oder Ziel egal",
    "related_pr": "PR-0012",
    "observed": "READ in synaipse forensics (BUG-0333, section 5): gate_git reads task-level verdicts as goal "
                "verdicts (team-kits/kernel/report.py ~:1870, parent lookup) and the newest verdict per kind wins; "
                "a full review+test pass on one order of PR-0020 (TSK-0472 or TSK-0488) would open a delivery merge "
                "of the whole goal, and a later passing order verdict would mask PR-0021's failing goal verdict "
                "EVD-0078. Read, not driven.",
    "expected": "A delivery merge of a goal rests on verdicts about the GOAL (or its united tree), and a failing goal "
                "verdict is not superseded by a passing verdict on one of its orders.",
    "repro": "Two EVDs: goal acceptance fail, then an order-level full pass of the same kind -> the gate's verdict "
             "reading for the goal.",
    "severity": "high",
    "acceptance_criteria": [
        {"id": "AC-1", "text": "an order-level pass does not mask a goal-level fail for a delivery merge -- a test "
                               "naming this bug, red on 2026.09.27-9"},
    ],
    "source": SRC,
    "limits": "Offen; im Feld noch nicht ausgenutzt (der synaipse-PM hat den Weg bewusst nicht genommen).",
}
HOLE = {
    "title": "Git-Verlauf ohne Merge: rebase, cherry-pick und merge-tree/commit-tree sieht die Liefer-Regel nicht "
             "-- eine Umgehung der Pruef-Pflicht vor der Lieferung",
    "related_pr": "PR-0012",
    "observed": "READ/OBSERVED in synaipse forensics (BUG-0333, sections 3 and 5): the dev-kit's gate_git fires on "
                "git push/merge only (_compat.py ~:2235); rebase and cherry-pick move commits into a branch without "
                "it, and the synaipse QA role built a composite state with `git merge-tree --write-tree` + `git "
                "commit-tree` (agent transcript line 124) the rule never saw. The PM refused rebase/cherry-pick as a "
                "bypass. VERDICT: open; belongs to the integration stream of wave 1 (integration branch + verdict "
                "on the united tree), and to stream B's after-check where history moves.",
    "expected": "Moving commits into a delivery branch by any git route meets the same verdict requirement as merge.",
    "repro": "In an installed dev-kit project: `git cherry-pick <sha>` onto the integration branch with a failing "
             "goal verdict -> no refusal.",
    "severity": "medium",
    "acceptance_criteria": [
        {"id": "AC-1", "text": "rebase/cherry-pick onto a delivery branch meet the delivery verdict rule -- a test "
                               "naming this bug, red on 2026.09.27-9"},
    ],
    "source": SRC,
    "limits": "Offen bis Welle 1. Begrenzt: im Feld nicht benutzt fuer die Lieferung; Push braucht weiter die "
              "Freigabe des Nutzers.",
}

for body, extra in ((MASK, []), (HOLE, ["--hole"])):
    r = subprocess.run(BASE + extra, cwd=ROOT, env=env, input=json.dumps(body), capture_output=True, text=True,
                       encoding="utf-8")
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr[-800:])
    if r.returncode:
        sys.exit(r.returncode)
r = subprocess.run([sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "migrate-holes",
                    "--reindex"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-800:])
