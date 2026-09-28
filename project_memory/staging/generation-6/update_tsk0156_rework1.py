"""TSK-0156: add the rework-1 input after the verifier's FAIL (verify-round-1.md, 2026-09-27 16:55)."""
import json
import os
import subprocess
import sys

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "update", "TSK-0156"]
env = dict(os.environ, PYTHONPATH="team-kits")

with open(os.path.join(ROOT, "project_memory", "tasks", "active", "TSK-0156.yaml"), encoding="utf-8") as fh:
    item = yaml.safe_load(fh) or {}

REWORK = (
    "REWORK 1 (added 2026-09-27 16:5x by the lead after the verifier's FAIL, "
    "project_memory/staging/TSK-0156/verify-round-1.md -- read it by section): fix F4 = BUG-0326 "
    "(sweep_expired_leases strands CHILD_WAITING; the WAITING branch of dispatch names the FAILED way out) with a "
    "test naming BUG-0326, red first in a copy under the round-scratch dir, and run EVERY suite that reads the "
    "dispatch/lease predicates you change as its own selection (DEC-0080 rule 2: grep the callers). Also the low "
    "findings, since each is one site: F1 (tools/test_light_kit.py:890 comment vs the document-card read text that "
    "still shows a staging path -- fix the card or the comment, measured), F2 (tools/test_presets.py:712/:761 refer "
    "to the removed _preset_target_form), F3 (upkeep --help refused to a subagent; the 'Parsing prints nothing' "
    "claim gets a test that the silencing mutation turns red), F5 (kernel/__init__.py:12 'whichever route' vs a "
    "'.CLAUDE' import leaving .pyc -- make it true or say the limit). The verifier also saw "
    "test_gate1_places_a_tilde_word_where_the_shell_puts_it hang > 9:42 in real `bash -c` calls in its copy: "
    "run that node alone in the main tree with a timeout and record the time or the hang. Re-stamp once at the end. "
    "Protocol: append a 'Rework 1' section to staging/TSK-0156/protocol.md as you go."
)
EXPECTED = (
    "rework 1: BUG-0326 fixed with its naming test (red-before measured), F1/F2/F3/F5 closed or named as a limit, "
    "the reading suites of every changed predicate green with clock times, one re-stamp, validate + ruff clean, "
    "the full run NOT started"
)
body = {
    "required_inputs": list(item.get("required_inputs") or []) + [REWORK],
    "expected_outputs": list(item.get("expected_outputs") or []) + [EXPECTED],
}
r = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(body), capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr[-1500:])
sys.exit(r.returncode)
