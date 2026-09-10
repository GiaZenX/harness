"""TSK-0133 (DRAFT, the generation-5 merge round) grows two required_inputs lines: the TSK-0131 round-4
residues the merge verifier measures (DEC-0088 (c): no fifth stream round) and TSK-0130's state (round 3
pending the cloud routines; the consistent package of 19:04 is what the merge takes). The list is read
from the item and appended -- `update` replaces the field. Body on stdin to `kernel.cli update TSK-0133`."""
import json
import os
import subprocess
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ITEM = os.path.join(ROOT, "project_memory", "tasks", "active", "TSK-0133.yaml")
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "update", "TSK-0133"]

NEW_LINES = [
    "TSK-0131 round 4 (verify-round-4.md, 2026-09-06): FAIL without a blocking finding; the four residues "
    "N4-1 (tools/test_migrate.py: a second finding about the receipt must pass the receipt filter -- built, "
    "mutation RED), N4-2 (tools/test_review_procedure.py: _own_block reads the PARAGRAPH, not the lead-in "
    "span -- seam N18 tightened: a kit owes ONE bold statement carrying BOTH axes in itself), N4-3, N4-4 were "
    "fixed by the implementer WITHOUT a fifth stream round (lead decision per DEC-0088 (c), round log 19:50) "
    "-- the MERGE VERIFIER measures N4-1 and N4-2 on the merged tree (mutation red-first, one change each); "
    "final patch stream-stock.patch 258 531 B / 37 files (20:07); TSK-0131's verifier tokens for rounds 1-3 "
    "are unknown (the reports name none) -- the (g) table says so, nothing is estimated",
    "TSK-0130 state at the merge cut: steps (1)/(2) done, package consistent (patch 31 files / 4287 lines, "
    "cut_check consistent: true, 19:04), verify round 3 PENDING the two cloud routines (RemoteTrigger list "
    "empty five times on 2026-09-06; the user creates them in the claude.ai UI) -- radar/routine.json is "
    "recorded by the LEAD when they exist and is NOT a merge blocker (data, no code); this generation's new "
    "holes beyond H185: BUG-0269/H186 (desktop scheduled task, suffix-less report), BUG-0270/H187 (the "
    "pointer sweep reads docs and the kits tree only, 39 unread test pointers under tools/, depends on H175); "
    "`migrate-holes --reindex` was already run by G5-2 at 17:36 (176 holes; the index rows link docs/holes/"
    "H<n>.md that exist only to H165 -- BUG-0258/H176 class) -- run again after the merge's own H188+",
]


def main():
    with open(ITEM, encoding="utf-8") as fh:
        item = yaml.safe_load(fh)
    inputs = list(item["required_inputs"])
    for line in NEW_LINES:
        if line not in inputs:
            inputs.append(line)
    body = {"required_inputs": inputs}
    env = dict(os.environ, PYTHONPATH="team-kits")
    result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(body),
                            capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(result.stdout[-800:])
    sys.stderr.write(result.stderr[-1500:])
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
