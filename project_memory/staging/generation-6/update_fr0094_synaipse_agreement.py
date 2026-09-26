"""FR-0094: record the synaipse PM's agreement (pasted by the user 2026-09-26) through `kernel.cli update`."""
import json
import os
import subprocess
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "update", "FR-0094"]
env = dict(os.environ, PYTHONPATH="team-kits")

with open(os.path.join(ROOT, "project_memory", "inbox", "active", "FR-0094.yaml"), encoding="utf-8") as fh:
    current = (yaml.safe_load(fh) or {}).get("request_text", "")
if not current:
    sys.exit("FR-0094 carries no request_text -- nothing written")

ADDED = (" || AGREED 2026-09-26 (synaipse PM's answer, pasted by the user): synaipse builds the comment tool FIRST, "
         "standalone (one script that opens any HTML preview with the comment layer, no dependency on synaipse code, "
         "comments in a documented file: text, element, page, viewport, theme, screenshot path, open/done), recorded "
         "there as synaipse PR-0031 with this FR as its reference. The 'no approval while comments are open' lock is "
         "explicitly EXCLUDED there and stays with the kit. CORRECTION of the lead's earlier note: synaipse-unified "
         "runs kit 2026.09.13-6 since 2026-09-25, not 2026.07.18-3 (the survey read a stale file), so the kit can take "
         "the tool over later and it returns to synaipse through a normal kit update. Kit half of this FR: adopt the "
         "proven tool into the dev-team kit + the freeze lock on open comments.")

r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps({"request_text": current + ADDED}),
                   capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
