"""Two user decisions of 2026-09-06, captured through the kernel: (1) FR-0012 decision catcher = option A
(a `work` field on DEC + the pointer-direction detector); (2) the watcher trigger = a CLAUDE ROUTINE,
'like the project auditor should run' -- with the user's question 'does it run at all?' turned into
a measurement duty for the stream. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

CATCHER = {
    "title": "FR-0012 entschieden: eine Entscheidung sagt in einem Feld `work`, welche Items sie tragen (oder `none`), "
             "und der Validator nennt jede geltende Entscheidung, auf die kein Item zeigt -- Feld plus Zeiger-Erkennung (A)",
    "context": "USER DECISION 2026-09-06 on the DEC-first proposal of stream G5-1 (TSK-0131, "
               "staging/TSK-0131/dec-decision-catcher.json). The measured case: DEC-0034 stood VALID for 26 "
               "days while nothing built it and no item pointed at it (DEC-0080). Measured at b7f282e: "
               "validate has no line about a DEC except the supersedes shape; a DEC has no automaton, no "
               "parent binding and no field saying whether it commits anyone to work. Options: (A) a field "
               "`work: none | [item ids]` -- required for new captures, optional for stored items, ids resolved "
               "like every other binding; validator: `work` naming a missing id = error; a DEC in force with "
               "no `work` and no item naming it = warning 'decision without a carrier'; `work: none` is "
               "silent; (B) a phrase class over prose -- rejected (no heuristic over prose, FR-0010); (C) "
               "pointer direction only, no field -- no honest silence for a decision that demands nothing. "
               "The user chose (A).",
    "decision": "(1) OPTIONAL_FIELDS['DEC'] gains `work`; capture DEC requires it (`none` or a list of item "
                "ids the kernel resolves); stored decisions stay valid without it. (2) validate: (a) a `work` "
                "id no item carries -> error; (b) a DEC in force, `work` absent, and no item anywhere names "
                "the DEC -> warning 'decision without a carrier' with the DEC id; (c) `work: none` silences "
                "(b). (3) Built red-first in kernel/report.py + backlog_types.py + the capture surface by "
                "TSK-0131; shipped to the three kits as kernel code; the lead skills say the field in the "
                "DEC step. (4) What stays human, said in the text: a `work: none` on a decision that does "
                "demand work. (5) The decisions of generation 4/5 that DO demand work (DEC-0071..0079, "
                "DEC-0081, DEC-0082, this one) get their `work` written by the stream through `update` once "
                "the field exists -- the survey of G5-1 feeds it.",
    "consequences": "The DEC-0034 class is caught by both halves (no field, no carrier). Cost: one field, one "
                    "validator line, a capture duty. Rejected: (B) prose heuristics; (C) no silence.",
    "source": "staging/TSK-0131/dec-decision-catcher.json; user answer 2026-09-06 'A -- Feld + Zeiger-Erkennung'; "
              "FR-0012; PR-0008 AC-7; DEC-0080; DEC-0034",
}

ROUTINE = {
    "title": "Radar-Ausloeser entschieden: die Watcher laufen ueber eine CLAUDE-ROUTINE -- 'so wie auch der "
             "Project Auditor laufen sollte' -- und ob der Auditor in den Kits ueberhaupt laeuft, wird zuerst "
             "gemessen; kein Windows-Task, keine Sitzungsstart-Pflicht des Leads als Mechanismus",
    "context": "USER DECISION 2026-09-06 on the DEC-first proposal of stream G5-2 (TSK-0130, "
               "staging/TSK-0130/dec-trigger.json), which offered (A) a lead session-start routine and (B) a "
               "Windows Task Scheduler entry running `claude -p` headless (probe task measured). The user "
               "chose NEITHER as offered: 'Wie jetzt auch: ueber eine Claude Routine! So wie auch der "
               "Project Auditor laufen sollte! Macht er das ueberhaupt?'. Measured facts the stream and the "
               "lead hold: no mechanism has ever started a watcher (14 dated reports, all human-started; no "
               "cron in the session, no OS task); the kits carry a ROUTINE mechanism (spec II.2: a routine "
               "bound to a role, hooks/_routine.py + session_status.py -- 'the hook reports, the PM spawns', "
               "FR-0038 / TSK-0112 run record; the project-auditor routine declared 'weekly + after kit "
               "update'); H158 (G4-3) measured that no occasion makes the AUDIT run due in this repo; "
               "Claude Code's own session cron (CronCreate) does not outlive the session; the platform also "
               "offers scheduled routines outside a session (RemoteTrigger / cloud routines) -- NOT measured "
               "yet on this host.",
    "decision": "(1) The mechanism is the platform's ROUTINE, the same shape the kits use for the "
                "project-auditor: a routine declared in the repo (role, trigger, cadence) that the platform "
                "surfaces as due and that starts the watcher -- not a Windows task, not a prose duty. (2) "
                "TSK-0130 MEASURES FIRST, before building: (a) what a 'Claude routine' is on this host today "
                "-- the kits' _routine.py / session_status.py feed (surfaced at session start, dispatched by "
                "the lead role), Claude Code's session cron, and the platform's scheduled routines outside a "
                "session (RemoteTrigger / cloud) -- which of them survives a session end and a week without "
                "a session, with a probe each; (b) the user's question: does the project-auditor routine "
                "actually RUN in a scaffolded kit project -- is it declared, does session_status report it "
                "due after its cadence, does the PM spawn it -- measured on a dev pilot as a process, the "
                "answer written into the protocol and, if it does not run, captured as a hole item with "
                "the chain. (3) Then the watchers get the routine that the measurement shows works: "
                "declared in this repo (radar/ or tools/, plus the lead's registration where the platform "
                "needs one), a test refusing any schedule sentence the declaration does not back, one "
                "end-to-end run started by the mechanism. (4) If no platform routine survives a week "
                "without a session, the stream reports that as the measured limit and proposes ONE more "
                "time (with the auditor's real behaviour on the table) rather than building option B "
                "silently.",
    "consequences": "Watchers and auditor share one trigger shape -- one mechanism to maintain, one class of "
                    "claim to test; the user's question about the auditor gets a measured answer instead of "
                    "a shrug. Cost: one more measurement round in TSK-0130 before the build. Rejected by the "
                    "user: the OS task (B) and the lead's session-start duty (A) as the mechanism.",
    "source": "staging/TSK-0130/dec-trigger.json; user answer 2026-09-06; FR-0088; PR-0010 AC-1; DEC-0080; "
              "H158 (BUG item of the migration); spec II.2 routines; FR-0038 / TSK-0112",
}

env = dict(os.environ, PYTHONPATH="team-kits")
for body in (CATCHER, ROUTINE):
    result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(body),
                            capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        sys.exit(result.returncode)
