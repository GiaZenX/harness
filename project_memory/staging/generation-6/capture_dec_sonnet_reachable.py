"""Capture the correction TSK-0136 surfaced (protocol section 6, residue 5): DEC-0095 (1) 'build starts on opus'
was built as the FLOOR of the derivation, so the PM's ask `rung: sonnet` for a small slice comes back opus in
dev/research -- the user's 'Sonnet nur fuer ganz kleine Sachen' (2026-09-11, FR-0091) and DEC-0091's three-line
rule became unreachable for build roles. Decision: DEFAULT and FLOOR are two values. Body on stdin to
`kernel.cli capture DEC`, work = the carrier order created next. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Bau-Klasse: STANDARD und BODEN sind zwei Werte (Praezisierung zu DEC-0095 (1) / DEC-0091 (2)): der Bau "
             "startet ohne Bitte auf opus, der Boden bleibt der Rollen-Pin (sonnet), und eine Bitte UNTER den Standard "
             "bis zum Boden ist erlaubt, wenn der Auftrag einen Test als Abnahme traegt -- sonst bliebe 'Sonnet fuer "
             "ganz kleine Sachen' fuer Bau-Rollen unerreichbar",
    "context": "MEASURED by TSK-0136 (protocol section 6, residue 5; pilot rig): with dev/research ladder.yaml "
               "`build: opus` the derivation `start = max(floor, ask)` takes opus as the FLOOR, so "
               "`create-task --rung sonnet` on a build order is answered with opus -- DEC-0091 (2) said 'a PM can lift "
               "an order, never lower a role below its class', and DEC-0095 (1) moved the class start to opus, which "
               "together made the lowest rung unreachable for builders. The user's words the same morning (FR-0091): "
               "'Sonnet nur fuer ganz kleine Sachen -- gut, aber manchmal etwas daemlich'; Anthropic's guidance "
               "(research A): Sonnet for mechanical, precisely describable edits ('if you could describe the diff in "
               "one sentence'); practice (research B): Sonnet as the executor of narrow, test-carrying slices. The "
               "three-line rule in the PM texts still offers 'sonnet high/xhigh' -- a text promising what the "
               "dispatcher refuses (house rule 3).",
    "decision": "(1) TWO VALUES for the build class in every ladder: `build: {default: opus, floor: pin}` (dev, "
                "research; office keeps `build: pin` = default and floor both pin, DEC-0078) -- the ladder reader "
                "accepts the old scalar form as 'default = floor = value' so nothing shipped breaks, and the two-ended "
                "tripwire covers both spellings. (2) DERIVATION: no ask -> start = default; ask above default -> "
                "max(default, ask) capped by top (as today); ask BELOW default -> allowed down to the floor ONLY when "
                "the order carries a test-shaped acceptance (an expected_output naming a test file or `--acceptance-ref` "
                "to an AC with a test) -- a description alone keeps the default; the refusal names the rule. The lease "
                "`why` says 'the order asks sonnet below the default opus; allowed: acceptance is a test'. Escalation "
                "climbs from wherever the order starts (DEC-0096). (3) The checkpoint's line (c) shows default, floor "
                "and ask side by side, and the self-question carries Anthropic's two signals (FR-0091 precision 1). "
                "(4) `report.lease_distribution` counts per rung AND per effort (TSK-0136 residue 1). (5) The reading-"
                "discipline paragraph reaches the harness-verifier text too (residue 4). (6) Item hygiene: the "
                "research-team PM file is agents/project-manager.md (residue 2); tools/test_model_pins.py is in scope "
                "(residue 3); run_2's label (residue 8). CARRIER: one small Opus order under PR-0011.",
    "consequences": "Sonnet stays reachable exactly where the research and the user put it -- narrow, test-carrying "
                    "slices -- and unreachable where a description is all there is; the default stays opus without "
                    "the PM asking. Cost: one more field shape in three ladders, one branch in the derivation, one "
                    "reader change. Rejected: keeping the floor at opus (contradicts the user's rule and Anthropic's "
                    "guidance); making sonnet the default again (the measured first-round failure rate and the "
                    "cost-per-solved-task numbers favour opus).",
    "work": ["PR-0011"],
    "source": "project_memory/staging/TSK-0136/protocol.md section 6; DEC-0095; DEC-0091; DEC-0096; DEC-0078; "
              "staging/FR-0091/summary.md (precisions 1 and 2); user message 2026-09-11 ~09:00",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
