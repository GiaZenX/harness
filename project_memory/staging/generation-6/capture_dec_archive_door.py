"""The user's archive-door decision of 2026-09-26 (question asked by the lead before order 6): a narrow, audited
kernel door that may correct ONLY a test reference in an archived item. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Archiv-Tuer: ein schmaler Kernel-Befehl darf in einer archivierten Akte NUR einen Testverweis "
             "(regression_tests / Testknoten) auf einen existierenden Nachfolger korrigieren, protokolliert; alles "
             "andere im Archiv bleibt unantastbar, und der Test 'jeder genannte Test existiert' bleibt scharf",
    "context": "USER 2026-09-26 ~07:3x, answer to the lead's question with three options (narrow correction door / "
               "stop checking the archive / keep the old name as an alias test): 'Schmale Korrektur Tuer'. MEASURED: "
               ".claude/hooks/test_gates.py::test_every_test_a_hole_names_is_one_that_exists is red because archived "
               "BUG-0221 (H138, ACCEPTED_EXCEPTION) and BUG-0237 (H155, VERIFIED) name tests that were renamed or "
               "replaced after they were archived; the kernel has no door to an archived item (handover 2026-09-13).",
    "decision": "(1) A kernel command (name is the builder's, e.g. `amend-archived-test-ref`) that takes an archived "
                "item id, the OLD test node and the NEW test node, and refuses unless: the item is archived; the old "
                "node is named in that item's test-reference field(s) and resolves NOWHERE; the new node RESOLVES "
                "(collectable) now; nothing but that reference changes. (2) Every use writes an audit record "
                "(who, when, old -> new, reason) the index and the hole list can show. (3) No other field of an "
                "archived item becomes writable -- status, verdict, evidence and approvals stay frozen; a test "
                "(red-first) proves each refusal. (4) The gate test that every named test exists keeps reading "
                "archived items: a deleted regression test of a closed bug stays visible. (5) First use: H138 "
                "(BUG-0221) and H155 (BUG-0237), done by the lead through the new command after the verifier's PASS.",
    "consequences": "The archive stays history, but its pointers can follow a rename; the gate suite turns green "
                    "without weakening. Rejected: not checking the archive (a deleted regression test would go "
                    "unnoticed); alias tests under old names (ballast in code).",
    "work": ["PR-0012"],
    "source": "user answer 2026-09-26; handover 2026-09-13 ('Handback im Archiv'); staging/TSK-0151/gates-run-final.txt",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr[-1500:])
sys.exit(result.returncode)
