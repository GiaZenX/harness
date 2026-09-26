"""The user's approval feedback of 2026-09-26 (working in synaipse-unified), measured by the lead. Two thin FRs.
Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "FR"]

MEASURED = ("MEASURED by the lead 2026-09-26 in C:/Offline Repos/synaipse-unified/project_memory/approvals (kit "
            "2026.09.13-6), 2026-09-25 20:29 -> 2026-09-26 13:09: 16 minted approvals = 1 plan, 2 delivery, "
            "1 kit_update, 1 routine and 11 SCOPE -- one per item: CR-0001..CR-0009, BUG-0001, PR-0031; nine of them "
            "created 21:01:19-21:03:15, i.e. nine questions in two minutes. The kernel's list-bound form covers only "
            "`plan` (the open ROOT goals, approvals.plan_goals), `verification` and `hole_exception` batches; a scope "
            "question over CRs/BUGs/new goals has no batch form, so the PM had no way to ask once. Earlier work on "
            "the card's language: BUG-0073, BUG-0271 (both VERIFIED), FR-0090 (expiry date readable, TRIAGED).")

FRS = [
    {
        "title": "Freigabe-Karte ruhig und lesbar: 'Freigabe erbeten fuer <Art>', darunter die Liste der Eintraege "
                 "(Id + deutscher Kurztitel), dazu eine vom PM formulierte Erklaerung, was das bedeutet -- keine "
                 "Pruefsummen, Pfade, Request-Ids und englischen Feldtexte im Blickfeld",
        "request_text": "User 2026-09-26: 'Die Freigaben wirken immer noch ziemlich ueberfordernd, ziemlich "
                        "Reizueberflutung. Es waere einfach nur wichtig: Freigabe erbeten fuer, und dann steht unten "
                        "aufgelistet, welche Tasks, Requirements oder was auch immer freigegeben werden, und auch noch "
                        "eine vom PM selbst formulierte Nachricht, was das alles bedeutet.' EXAMPLE of today's card "
                        "(this repo, 2026-09-25): the option text carries 'Gebunden an Pruefsumme abf3255a86e2... "
                        "(Anfrage approvals/pending/<32 hex>.yaml)', the question an '[APR-REQ:<32 hex>]' token, and "
                        "for a hole exception the English `limits` sentences cut at 160 characters. CONSTRAINT to keep: "
                        "gate_approval compares the answered question character for character and mints only from the "
                        "approving option -- the binding (request id, mint code, hash) must stay machine-checkable, but "
                        "may move out of the READ text (e.g. only the short mint code in the label, the rest in the "
                        "record). The PM's note must be INSIDE what is signed (hashed), so the user signs the words he "
                        "read, and marked as the PM's words. " + MEASURED,
        "source": "user message 2026-09-26 (Desktop session, while working in synaipse-unified); kernel/approvals.py "
                  "build_question; BUG-0073; BUG-0271; FR-0090",
    },
    {
        "title": "So autonom wie moeglich freigeben: EIN Ja zum Projekt deckt alles darunter; was unterwegs neu "
                 "entsteht (CR, BUG, neues Ziel), sammelt der PM und fragt EINMAL als Sammel-Freigabe -- nie neun "
                 "Einzelfragen hintereinander",
        "request_text": "User 2026-09-26: 'Ich habe immer noch das Gefuehl, dass man sehr viel auf einmal freigeben "
                        "muss, obwohl ich mir das eher so autonom wuensche wie moeglich, sprich: Man committet sich auf "
                        "ein Projekt, man gibt alles auf einmal irgendwie frei, und neue Feature Requirements, System "
                        "Requirements, sowas legt er an und gibt sie dann natuerlich separat frei, falls waehrend des "
                        "Prozesses was festgestellt wird. Aber dann wird immer noch alles auf einmal freigegeben.' "
                        "LEAD'S READING: (1) a SCOPE BATCH (`request-approval scope --batch <ids>`, the same list-bound "
                        "form as verification/hole_exception, each entry bound to its own scope hash) so every scope "
                        "question of a phase is ONE card; (2) the PM's playbook collects new CR/BUG/goal scope questions "
                        "and asks them together at a natural break, not one per capture; (3) a DECISION for the user: "
                        "does the plan approval of a goal also cover items that stay INSIDE that goal's accepted "
                        "criteria (e.g. an SR or a bug fix that changes no acceptance criterion), so only real scope "
                        "changes ask at all? " + MEASURED,
        "source": "user message 2026-09-26; synaipse-unified/project_memory/approvals (16 records); "
                  "team-kits/kernel/approvals.py (plan_goals, content_question, PLAN_COVERED_KIND)",
    },
]

env = dict(os.environ, PYTHONPATH="team-kits")
rc = 0
for body in FRS:
    result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(body),
                            capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr[-1500:])
    rc = rc or result.returncode
sys.exit(rc)
