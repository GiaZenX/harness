"""FR-0094: add the answers the user gave to the SAME idea in the synaipse-unified session (2026-09-26), pasted here.
Merges a `source` line and extends `request_text` through `kernel.cli update` (body on stdin)."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory"]
env = dict(os.environ, PYTHONPATH="team-kits")

import yaml  # noqa: E402  (read-only: the kernel stays the only writer)

with open(os.path.join(ROOT, "project_memory", "inbox", "active", "FR-0094.yaml"), encoding="utf-8") as fh:
    current = (yaml.safe_load(fh) or {}).get("request_text", "")
if not current:
    sys.exit("FR-0094 carries no request_text -- nothing written")

ADDED = (" || SAME WISH IN synaipse-unified (the user asked that repo's PM the same day and pasted its answers here, "
         "2026-09-26): the user asked whether '#' should take a SCREENSHOT rather than change the design "
         "interactively. Agreed shape there, with the user's picks: (1) '#' -> comment box at the cursor, click the "
         "spot; (2) a numbered pin marks it; (3) on save an automatic SCREENSHOT of the visible area with the pin drawn "
         "in; (4) stored with it: the exact element, page, viewport size, light/dark theme; nothing in the design is "
         "overwritten (what was there and what was meant stay distinguishable); the PM turns collected comments into "
         "change requests the user decides; a PREVIEW-only tool, absent from the finished app. User picks: 'Pin + "
         "Screenshot', 'Nur am Computer' (no mobile long-press), build 'direkt nach dem Umzug' (synaipse's own "
         "migration, before its P1 acceptance). OVERLAP: synaipse is developed with this repo's dev-team kit (still "
         "2026.07.18-3, and its masterplan excludes a kit upgrade during its integration) -- one tool built twice is "
         "the risk; the lead proposes to the user where it is built first.")

body = {"request_text": current + ADDED}
r = subprocess.run(KERNEL + ["update", "FR-0094"], cwd=ROOT, env=env, input=json.dumps(body),
                   capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
