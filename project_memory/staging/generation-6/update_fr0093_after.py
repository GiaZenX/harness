"""FR-0093: record the AFTER measurement (2026-09-26 19:23) through `kernel.cli update`."""
import json
import os
import subprocess
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "update", "FR-0093"]
env = dict(os.environ, PYTHONPATH="team-kits")

with open(os.path.join(ROOT, "project_memory", "inbox", "active", "FR-0093.yaml"), encoding="utf-8") as fh:
    current = (yaml.safe_load(fh) or {}).get("request_text", "")
if not current:
    sys.exit("FR-0093 carries no request_text -- nothing written")

ADDED = (" || BUILT in TSK-0151 (0a79fc5): the three order lines in every kit's lead skill + this repo's lead role "
         "(user patch 2), tools/measure_agent_tokens.py. MEASURED 2026-09-26 19:23 with that tool (JSON in "
         "staging/TSK-0152/fr0093-*.json), per order, all subagents whose first prompt names the order: BEFORE "
         "TSK-0150: 2 agents, 664 turns, median of agent medians 284,281 tokens/turn, input 189.1 M, polling 6.4 %%. "
         "AFTER TSK-0151: 9 agents (3 verify rounds + 4 reworks), 847 turns, median 134,164, input 160.8 M, polling "
         "0.8 %%. AFTER TSK-0152: 6 agents, 629 turns, median 107,344, input 118.8 M, polling 4.2 %%. Reading: context "
         "per turn fell by 53-62 %% (fresh reworks 59-214 k median vs a resumed builder's 381 k); total input fell 15 %% "
         "on an order with twice the rounds and 37 %% on a comparable one. What still costs most: the FIRST builder of "
         "an order (TSK-0151 340 k, TSK-0152 304 k median; 73 M and 80 M input) -- a long single context. Next lever, "
         "not built: cut the first build into checkpointed parts handed to fresh agents.")
body = {"request_text": current.replace("%%", "%") + ADDED.replace("%%", "%")}
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(body), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
