"""Capture the correction of 2026-09-06 evening: the radar watcher DOES run through a routine -- a LOCAL
Claude Desktop scheduled task, Fridays ~20:00, since 2026-06-30 -- and the user's answer 'so wie beim Radar
watcher' meant exactly that. DEC-0085 (cloud routine) rested on a measurement error and is superseded.
Body on stdin to `kernel.cli capture DEC` with the `work` door (DEC-0083). Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Radar-Ausloeser, dritte Runde (loest DEC-0085 ab): der Mechanismus IST die LOKALE Claude-Desktop-Routine "
             "('Weekly harness radar', freitags ~20:00, seit 2026-06-30 durch den Sitzungsagenten angelegt) -- sie laeuft "
             "nachweislich; die Codex-Haelfte bekommt dieselbe Art Routine; die Cloud-Routine wird NICHT angelegt",
    "context": "USER 2026-09-06 ~20:15: 'Der radar watcher lief multiple male und das ganz automatisch freitags um 20 Uhr, "
               "ueber eine lokale Claude Routine! Es liegt ein Missverstaendnis vor. Den hat damals der Sitzungsagent dieses "
               "Repos angelegt, vor 2-3 Monaten.' MEASURED by the lead at once: (a) C:/Users/zenti/.claude/scheduled-tasks/"
               "radar-watcher/SKILL.md, 2026-06-30 10:53, a Claude Desktop LOCAL scheduled task whose body says 'Follow "
               ".claude/agents/radar-watcher.md exactly' -- so its reports carry the `-claude` suffix that definition names "
               "(BUG-0269's sentence 'the report carries no watcher suffix' read the SKILL's literal `radar/<today>.md` and "
               "not the definition it delegates to -- FALSE); (b) file mtimes of the Friday reports: 07-17 20:10, 07-24 "
               "20:12, 07-31 20:16, 08-07 20:47, 08-21 20:16, 08-28 20:12 -- eight Friday reports in nine weeks plus a "
               "Sunday 08-16 20:25 (the docs' catch-up run after a missed time) -- the deterministic few-minute offset "
               "after 20:00 the documentation describes (code.claude.com/docs/en/desktop-scheduled-tasks: 'Desktop checks "
               "the schedule every minute while the app is open ... Each task gets a small delay of a few minutes after "
               "the scheduled time'); (c) the docs: schedule, folder, model and enabled state are NOT in the SKILL.md -- "
               "they live in the app; a task fires only while the Desktop app runs and the machine is awake, one catch-up "
               "run within seven days; tasks can be created in the app's Routines page (New routine -> Local) or by asking "
               "Claude in any DESKTOP session; a remote session cannot. THE MEASUREMENT ERROR behind DEC-0085: the lead and "
               "G5-2 concluded 'no report was started by a mechanism' from the repo's audit log (no spawn events) and the "
               "empty RemoteTrigger list -- both look in the wrong place: a Desktop task starts its own session, which "
               "writes no spawn event into this repo's audit log, and it is not a cloud routine. The Friday cadence stood "
               "in radar/ the whole time and was not read. The user's answer of the second round ('So wie beim Radar "
               "watcher. So eine Routine.') meant this local routine; the lead read it as the cloud routine because he had "
               "told the user the radar ran through none.",
    "decision": "(1) The mechanism is the LOCAL Claude Desktop scheduled task, one per watcher: the radar half EXISTS and "
                "runs (Fridays ~20:00 since 2026-06-30, folder this repo, prompt = SKILL.md delegating to "
                ".claude/agents/radar-watcher.md); the CODEX half gets the same kind of task -- name `codex-watcher`, "
                "body delegating to .claude/agents/codex-watcher.md, weekly on SATURDAY ~20:00 (not the same evening: "
                "the app skips a task while another scheduled task is running), report radar/<date>-codex.md -- created "
                "by the USER in the Desktop app's Routines page or by asking Claude in a local Desktop session at the "
                "next restart; the lead cannot create it from a remote session (the schedule lives in the app). (2) The "
                "cloud routine of DEC-0085 is NOT created; it is the rejected alternative (runs with the machine off, but "
                "against a fresh clone with the report as a PR -- more moving parts for a repo the user works in daily). "
                "DEC-0085's declaration code (tools/radar_routine.py --describe, the cloud spec) is not the mechanism and "
                "may stay only as a documented option that says so; nothing in the repo may call the cloud routine 'the "
                "mechanism'. (3) Texts and record shape: radar/routine.json records the desktop tasks (kind desktop_task, "
                "path, watcher, schedule AS TOLD BY THE USER with its source, first/last measured report); `starts_itself` "
                "is true for a watcher whose desktop task exists AND whose reports show the cadence -- with the named limit "
                "that the schedule itself is not readable from disk and a week with the app closed is silent (the "
                "catch-up run covers seven days); `--due` stays the in-session check. (4) BUG-0269/H186 is corrected: the "
                "suffix claim goes; what stays true is 'fires only with the app open, schedule not on disk' -- as a "
                "documented limit, not a hole; the bound: the report cadence in radar/ is the evidence, read by `--due`. "
                "(5) CARRIER: the merge TSK-0133 rewrites the G5-2 texts that name the cloud routine as the mechanism "
                "(radar/README.md, tools/radar_routine.py describe text, the desktop-task test's wording, "
                "dec-trigger-2.json's measured state) as a merge finding -- the fact no stream could see because the lead "
                "had measured it wrong; PR-0010 AC-1's end-to-end evidence is the radar half's Friday reports (already "
                "measured) plus the first codex report the new task writes. (6) The lead's process error is named in the "
                "generation-5 retrospective: a 'never ran automatically' claim must be measured against the artifacts' "
                "timestamps, not against one log.",
    "consequences": "No new infrastructure: the mechanism that has worked for nine weeks is recognised instead of replaced; "
                    "the codex half costs the user one form in the Desktop app. Cost: a week with the machine off stays "
                    "silent (one catch-up run within seven days). Rejected: the cloud routine (DEC-0085), the Windows task "
                    "(DEC-0084), a session-start duty of the lead (DEC-0084).",
    "source": "user message 2026-09-06 evening; C:/Users/zenti/.claude/scheduled-tasks/radar-watcher/SKILL.md; radar/ "
              "file mtimes 2026-07-17..2026-08-28; code.claude.com/docs/en/desktop-scheduled-tasks (fetched 2026-09-06); "
              "DEC-0084; DEC-0085; BUG-0269; staging/TSK-0130/stream-protocol.md section 3d; staging/TSK-0130/dec-trigger-2.json",
    "supersedes": ["DEC-0085"],
    "work": ["TSK-0133"],
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
