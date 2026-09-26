"""The user's decision of 2026-09-26 on what an approval IS in the kits, after the lead's critique. Not idempotent."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Eine Freigabe ist ein VERSTAENDNIS-Abgleich, keine Arbeitserlaubnis: kein 'fertig mit X, weiter mit "
             "Y -- Freigabe?'; Fehler ohne Freigabe; Aenderungswuensche des Nutzers sofort anlegen (mit seinen "
             "Worten) und beginnen, gesammelt auf EINER ruhigen Karte bestaetigen, spaetestens vor der Abnahme",
    "context": "USER 2026-09-26, while working in synaipse-unified, three answers. (a) 'Die Freigaben wirken ... "
               "Reizueberflutung' and 'man muss sehr viel freigeben, obwohl ich mir das so autonom wie moeglich "
               "wuensche' (FR-0095, FR-0096). (b) Asked what the PM must still ask under an approved goal: 'Nur echte "
               "Aenderungen, und selbst gefundene Bugs ... werden auch direkt ohne Freigabe bearbeitet ... wenn ein "
               "User einen Bug meldet, wird er angelegt und naechstmoeglich bearbeitet, je nach Schweregrad ... Man "
               "setzt einen Plan auf, man legt los, und wenn der User sagt: Nee, das gefaellt mir nicht ... wird es "
               "notiert und der PM entscheidet, wann ... Aber die Freigabe erfolgt sozusagen sofort ... Hinterfrag "
               "das Ganze.' The lead's critique: agreed on bugs and on autonomy inside an approved goal; the two "
               "reasons the card still matters -- what the PM MAKES of the user's words can differ (synaipse CR-0001 "
               "carries 13 acceptance criteria written from a remark), and 'only the user's answer mints' is the "
               "kit's guard against an agent approving its own work. (c) On the lead's proposal: 'Was ich bloss "
               "nicht will, ist dieses: Ich bin jetzt mit dem und dem fertig. Ich wuerde jetzt mit dem und dem "
               "weitermachen. Freigabe? ... Die Freigabe war ja mehr so gedacht wie: Habe ich das richtig "
               "verstanden? ... Hey, du hast das und das gesagt, ich habe das und das verstanden. Hier finden wir "
               "uns auf einer Wellenlaenge. Nur um Missverstaendnisse zu vermeiden.' MEASURED: synaipse 2026-09-25 "
               "20:29 -> 09-26 13:09: 16 approvals, 11 of them scope, one per item, nine in two minutes.",
    "decision": "(1) WHAT AN APPROVAL IS: a check that PM and user understood the same thing -- never a permission "
                "to keep working. A PM (every kit) does NOT ask 'done with X, shall I continue with Y?'; it proceeds "
                "along the approved plan and reports. (2) THE ONLY QUESTIONS THAT REMAIN in the normal flow: the plan "
                "at the start (one card for all goals); a COLLECTED understanding card for the user's own change "
                "wishes and new goals (FR-0096 batch), asked at a natural break; the acceptance of a finished goal at "
                "the end; plus the kinds that are the user's by nature (push, kit update, routines, presets). (3) BUGS "
                "-- found by the team or reported by the user -- are captured and worked by severity WITHOUT an "
                "approval; a 'bug' whose fix changes behaviour the user accepted is a change wish and goes on the "
                "card. (4) A USER'S CHANGE WISH is captured at once WITH HIS VERBATIM WORDS and work may start at once; "
                "the understanding card ('you said ..., I understood ..., I made these items of it') must be answered "
                "before the goal's acceptance, not before the start. (5) THE GUARD STAYS: a card is still minted only "
                "by the user's answer (gate_approval); the PM never records a confirmation the user did not give. "
                "(6) THE CARD (FR-0095): 'Freigabe erbeten fuer <Art>', the list (id + short German title), the PM's "
                "own explanation inside what is signed; no checksums, paths or request ids in the read text. (7) "
                "Built with priority as the next kit order after order 6's delivery (the user feels it daily in "
                "synaipse); the builder greps every kit text that makes a PM ask for permission to continue and "
                "removes or rewrites it.",
    "consequences": "The user answers at three moments per goal (plan, collected changes, acceptance) instead of "
                    "once per item; work never waits on a click in the middle. Cost: work may start on a change the "
                    "user later corrects on the card -- bounded, because the card must be answered before "
                    "acceptance. Rejected: the user's chat words as the approval itself (would drop the guard "
                    "against self-approved work).",
    "work": ["PR-0012"],
    "source": "user messages 2026-09-26 (three answers); synaipse-unified/project_memory/approvals; FR-0095; "
              "FR-0096; kernel/approvals.py; DEC-0113 (recorded answers)",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr[-1500:])
sys.exit(result.returncode)
