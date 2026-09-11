"""Capture the user's word of 2026-09-11 ~12:45 on the watcher routines' schedule (changes DEC-0090 (4)): the Claude
and the Codex routines run AT THE SAME TIME; the next session runs in the Claude Desktop app, where the lead can
create the local tasks itself. Body on stdin to `kernel.cli capture DEC`, work = PR-0011 (AC-9's routine half).
Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Watcher-Routinen laufen GLEICHZEITIG (aendert DEC-0090 (4)): freitags ~20:00 beide Anbieter -- in Claude "
             "Desktop EINE lokale Aufgabe, die beide Watcher nacheinander faehrt (die App ueberspringt eine Aufgabe, "
             "solange eine andere laeuft), in der Codex-App zwei Automationen zur selben Zeit; angelegt vom Lead in der "
             "naechsten Desktop-Sitzung (Claude) und vom Nutzer in der Codex-App",
    "context": "USER 2026-09-11 ~12:45: 'Ich starte die naechste Session in der Desktop-App, so kannst du die Routinen "
               "direkt anlegen? Die Codex-Routine und die Claude-Routine sollen gleichzeitig laufen.' MEASURED: the "
               "radar routine of 2026-06-30 was created by a session running INSIDE Claude Desktop, which exposes the "
               "scheduled-task tools to the session; this remote/VS Code session has none (ToolSearch 2026-09-11); the "
               "Desktop docs (code.claude.com/docs/en/desktop-scheduled-tasks) say a run is SKIPPED while 'other "
               "scheduled tasks were already running' -- two Claude tasks at the same minute would lose one; the "
               "Codex app is a different app with its own scheduler (learn.chatgpt.com/docs/automations), so Claude and "
               "Codex runs CAN overlap. DEC-0090 (4) had staggered the four runs Fri/Sat/Sun/Mon to avoid exactly the "
               "Claude-side skip; the user prefers one evening.",
    "decision": "(1) ONE Claude Desktop task `watcher-duo` (the existing `radar-watcher` task is renamed or replaced), "
                "Fridays ~20:00, folder this repo: its instructions run claude-watcher FIRST and codex-watcher SECOND "
                "in the same session, each writing its own report (radar/<date>-claude-by-claude.md, "
                "radar/<date>-codex-by-claude.md); the lead creates it in the next Desktop session through the app's "
                "task tool and records it in radar/routine.json. (2) TWO Codex app Automations, both Fridays ~20:00 "
                "(claude-watcher-by-codex, codex-watcher-by-codex), created by the user in the Codex app from the "
                "--describe texts; whether the Codex app runs two automations concurrently is MEASURED at the first "
                "Friday (skipped-run entries), not assumed -- if it serialises, they stay as two entries and run back to "
                "back. (3) `tools/radar_routine.py --describe` and radar/routine.json carry the new schedule as told; "
                "--due keeps counting per watcher AND runner. (4) Nothing else of DEC-0090 changes (names, rungs, runner "
                "suffix, cadence evidence).",
    "consequences": "All four reports land on one evening and can be read side by side on Saturday; the Claude side "
                    "needs one task instead of two, which also removes the skip risk. Cost: a longer single Desktop "
                    "session on Fridays (two scans). Rejected: two Claude tasks at the same minute (measured skip rule); "
                    "keeping Sat/Sun/Mon (the user's word).",
    "work": ["PR-0011"],
    "source": "user message 2026-09-11 ~12:45; DEC-0090 (4)/(5); code.claude.com/docs/en/desktop-scheduled-tasks "
              "(skipped runs); learn.chatgpt.com/docs/automations; tools/radar_routine.py --describe (2026-09-11)",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
