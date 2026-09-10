"""Capture the user decision of 2026-09-06 on the closing route of a REPAIRED bug: option A -- a
user-minted scope approval per bug, relayed by the lead in a batch; B (an automaton edge for the
proven case) recorded as the question for DEC-0051 (2)'s own round. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Schliessweg eines reparierten Bugs entschieden: eine Nutzer-Muenzung (scope) je Bug, vom Lead "
             "gebuendelt vorgelegt -- der ausgelieferte Automat bleibt; die Kante TRIAGED -> FIXED fuer den "
             "bewiesenen Fall ist die Frage einer eigenen Runde (DEC-0051 (2))",
    "context": "USER DECISION 2026-09-06 on the proposal of stream G5-1 (TSK-0131, staging/TSK-0131/"
               "dec-bug-closing-route.json). MEASURED at b7f282e: AUTOMATA['BUG'] OPEN -> TRIAGED (free) -> "
               "APPROVED (user-minted 'scope' approval, one AskUserQuestion per bug relayed verbatim) -> FIXED "
               "(free) -> VERIFIED (passing test Evidence covering the bug; a declared selection counts since "
               "DEC-0071); the only terminals without a mint are REJECTED and DUPLICATE, which FR-0058 names a "
               "lie for a repaired bug. Generation 3 walked four bugs this way (APR-0001..0004), generation 4 "
               "one (APR-0006). Options: (A) mint per bug, batched -- nothing in the kernel changes; (B) an "
               "extra edge TRIAGED -> FIXED for a bug whose repair a passing Evidence already proves, with "
               "its own DEC and red-first test -- the round DEC-0051 (2) reserves; (C) leave them TRIAGED with "
               "the Evidence recorded and the 'stock lies upward' rollup naming them. The user chose (A).",
    "decision": "(1) A repaired bug walks the shipped route: the stream records the confirming Evidence "
                "(`evidence --kind test --result pass --related BUG-nnnn --run-scope selection`) and the "
                "re-measured chain via `update`; the lead relays `request-approval scope BUG-nnnn` for every "
                "repaired bug of the round in one sitting, each as its own verbatim AskUserQuestion; after "
                "each mint the kernel lines `transition FIXED`, `transition VERIFIED`, `archive` close it. (2) "
                "The kernel does not change for this. (3) Option B -- an automaton edge for the proven case, "
                "so the user approves repaired bugs collectively through the goal that shipped them -- is "
                "recorded as the question DEC-0051 (2)'s own round asks, with this round's count of mints as "
                "its measured cost. (4) Bugs whose repair still has to be built keep the scope mint as the "
                "authorisation of the fix work (DEC-0072's dispatch reads APPROVED).",
    "consequences": "Six mints in this round (the G5-1 list), each a click; the status field and the "
                    "derivation agree afterwards. Rejected for now: B (an automaton change without its own "
                    "round), C (two answers in the record, FR-0058's very defect).",
    "source": "staging/TSK-0131/dec-bug-closing-route.json; user answer 2026-09-06 'A -- Freigabe pro Fehler, "
              "gebuendelt'; FR-0058; PR-0008 AC-1/AC-6; DEC-0051; DEC-0071; APR-0001..0004, APR-0006",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
