"""Capture the user decision of 2026-09-06 on the radar trigger, second round: 'So wie beim Radar
watcher. So eine Routine. Eine Claude Routine. Geht das nicht?' -- measured answer: YES, the platform's
claude.ai code ROUTINE (RemoteTrigger) exists, recurs and outlives sessions; the radar watcher does NOT
run that way today (14 reports, all human-started; the account holds no routine). Decision: build it
(option B of dec-trigger-2.json) with the local routine (A) as the in-session half; the auditor's
read-only route (BUG-0266) stays its own item. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Radar-Ausloeser entschieden (zweite Runde): eine CLAUDE-ROUTINE der Plattform (claude.ai Code-Routine, "
             "RemoteTrigger) startet beide Watcher woechentlich in der Cloud gegen das GitHub-Repo und liefert den "
             "Bericht als Commit/PR; die lokale Routine (--due, Start durch den Lead) bleibt die Sitzungs-Haelfte; der "
             "Nur-Lese-Weg des Auditors (BUG-0266) ist ein eigenes Item",
    "context": "USER 2026-09-06, answering the second proposal (staging/TSK-0130/dec-trigger-2.json): 'So wie "
               "beim Radar watcher. So eine Routine. Eine Claude Routine. Geht das nicht?'. MEASURED by "
               "TSK-0130 and the lead: the radar watcher does NOT run through any routine today -- all 14 "
               "dated reports were human-started (radar/2026-09-05-codex.md line 10 says so for the codex "
               "half; no spawn events in the audit log; the account's RemoteTrigger list is empty); the kits' "
               "routine shape reports the auditor due and lets the PM start it only in a session; Claude "
               "Code's session cron dies with its session; the claude.ai code ROUTINE (RemoteTrigger: list / "
               "get / create / update / run / create_webhook_trigger / list_runs / get_run_log) exists on this "
               "account, recurs on a schedule, outlives every session, runs in a cloud sandbox that clones a "
               "REACHABLE remote repository and writes its result back as a commit / PR -- never into a local "
               "working tree. The lead corrected the proposal's claim that this repo is 'deliberately local "
               "only': origin = github.com/GiaZenX/harness.git, pushed 2026-09-05. The user did not pick the "
               "auditor repair (option C) in this answer; BUG-0266/H184 stays open with its chain.",
    "decision": "(1) The mechanism is the platform's Claude routine: a claude.ai code routine, created and "
                "owned by the lead through RemoteTrigger (the implementer roles have no such tool), scheduled "
                "weekly, running the watcher prompts headless in the cloud against origin/feat/harness-v2 (or "
                "the branch the routine names), committing the dated report to a branch and opening a PR "
                "that the lead reviews and merges at the next session; the local checkout receives it by "
                "pull. (2) The repo carries the routine's DECLARATION (tools/radar_routine.py --describe: both "
                "watchers, cadence, the exact prompt each cloud run gets, the branch/PR shape, "
                "`starts_itself` derived from the live trigger list the lead records), the test refusing any "
                "schedule sentence the declaration does not back, and the in-session half (--due, --run) as "
                "the fallback for a week the cloud routine misses. (3) TSK-0130 builds the declaration, the "
                "prompt texts, the PR-shape duty (what the cloud run may write: radar/<date>-<watcher>.md "
                "only, radar/decided.md never), the docs; the LEAD creates the routine with RemoteTrigger "
                "create from the declaration, runs it once with RemoteTrigger run, reads list_runs / "
                "get_run_log for the end-to-end evidence, and hands the verifier the run log and the PR. (4) "
                "The auditor's read-only dispatch route (`routine` approval kind, BUG-0266/H184) is NOT "
                "built in TSK-0130; it is the next item under PR-0010 or its own goal -- the lead puts it to "
                "the user at the generation-5 close-out. (5) Cost and limits named in the texts: a report "
                "arrives as a PR, not a file; the cloud run needs the remote reachable and the account's "
                "routine quota; the triage of reports stays the lead's.",
    "consequences": "The watchers run every week whether or not a session opens -- the first mechanism in "
                    "this repo's history that does. Cost: one routine on the account, a PR per report, the "
                    "lead's review at the next session. Rejected: A alone (a week without a session stays "
                    "silent), the OS task (the user's earlier word), an auditor repair inside TSK-0130 (scope).",
    "source": "user answers 2026-09-06 (two rounds); staging/TSK-0130/dec-trigger.json, dec-trigger-2.json, "
              "stream-protocol.md section 3; DEC-0084; radar/2026-09-05-codex.md; RemoteTrigger list "
              "2026-09-06 (empty); git remote origin",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
