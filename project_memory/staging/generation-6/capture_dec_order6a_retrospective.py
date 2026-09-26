"""Order 6a (TSK-0151) retrospective -- review EVENT: something was merged and released (commit 0a79fc5, rollout
2026-09-25 22:44). Four questions answered from the round log (staging/generation-6-streams.md, 2026-09-25 15:05 ->
22:44) and the verify reports. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Rueckschau Order 6a (TSK-0151): ein Auftrag, der einen Leser ueber Freitext bestellt, ist ein "
             "Schnittfehler des Leads -- bestellt wird ein struktureller Vertrag; frische Nacharbeiter kosten "
             "gemessen die Haelfte eines wiederaufgenommenen",
    "context": "MEASURED from the round log 2026-09-25: builder 15:05-~17:35 456 k; lead finding F1 17:40; rework F1 "
               "292 k; verifier 1 killed by the usage limit (18:27-~18:30, nothing written); verify 1 FAIL 205 k "
               "(V1-V8); rework 2 260 k; verify 2 FAIL 167 k (R2-1..R2-5); rework 3 142 k; verify 3 'FAIL, not "
               "blocking' 144 k; close-out 66 k; delivery run 64 min green (5163), gates 554/1 (pre-existing "
               "H138/H155). Sum of agent tokens ~1.73 M; wall clock 15:05 -> 22:44 = 7 h 39 min; 3 verify rounds, "
               "4 reworks (F1, 2, 3, close-out). Finding classes: (a) PROSE READERS AS SPELLING LISTS -- V3/V4 in "
               "round 1, R2-3/R2-4 in round 2: the order's expected_output 'no price figure in the file' and the "
               "header sentence 'no luna row' invited a test that searches free text, the class DEC-0112 already "
               "retired for negations; (b) THE RUNNING PATH -- the lead's own order suggested 'the Claude "
               "translation of the top rung' and said nothing about the lease/header; the builder cut the Codex "
               "top (F1), then V1 found the header without a provider: both are 'the order named a form, not the "
               "path that runs'. FR-0093 lever 1 applied for the first time: every rework was a FRESH agent "
               "(142-292 k) against the 500-750 k measured for resumed rework agents before.",
    "decision": "(1) AT THE CUT, an expected_output or AC that asks a test to find a property IN FREE TEXT (prices, "
                "negations, 'no X row', wording) is a lead error: the item asks for a STRUCTURAL contract instead "
                "(a key absent, a field present with source and date, a value in a closed vocabulary), and prose "
                "stays a review matter (DEC-0112 generalised from negations to every free-text property). (2) AN "
                "ORDER NAMES THE PATH THAT RUNS, not a form: when a decision changes what a role gets, the order "
                "says which readers of lease/header/dispatch must show it (DEC-0080 rule 1 applied to answers, not "
                "only to files), and does not suggest an implementation form. (3) FRESH REWORK AGENTS stay the "
                "rule (FR-0093 lever 1) -- the 'after' measurement of FR-0093 is taken on the next order with "
                "tools/measure_agent_tokens.py against the TSK-0150 baseline (median 284 k/turn). (4) A usage-limit "
                "kill is survivable when the report is written EARLY: every verifier order says so from now on.",
    "consequences": "Cheaper next round: one verify round saved per avoided prose reader (here two rounds, ~310 k + "
                    "~400 k rework). The price reader built in this order stays as it is with its limits in BUG-0309; "
                    "no further widening.",
    "work": ["PR-0012"],
    "source": "project_memory/staging/generation-6-streams.md 2026-09-25 15:05-22:44; staging/TSK-0151/verify-round-1.md, "
              "-2.md, -3.md, protocol.md; DEC-0102 (2); DEC-0112; DEC-0080; FR-0093",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr[-1500:])
sys.exit(result.returncode)
