"""Two defects the 2026-09-25 session measured, as BUG items under PR-0012 (Bug-Null): the tier table is stale against
the vendors and against DEC-0114; the routine tool's schedule table still carries DEC-0090 (4) after DEC-0098 (3).
Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "BUG"]

BUGS = [
    {
        "title": "Die Stufen-Datei der Kits ist veraltet: Codex-Sprossen auf GPT-5.6, Claude-Preisanker von Opus 4.1, "
                 "Fable als oberste Claude-Stufe -- DEC-0114 sagt, wie es richtig ist",
        "related_pr": "PR-0012",
        "observed": "MEASURED 2026-09-25 (radar/2026-09-25-claude-by-claude.md items 1/2, radar/2026-09-25-codex-by-claude.md "
                    "items 1/7, read against team-kits/model_tiers.yaml at 8677bd2): tiers.codex opus: gpt-5.6-sol, sonnet: "
                    "gpt-5.6-terra while GPT-6 Sol/Luna are GA (2026-09-22) and the Codex CLI prompts migration off 5.6; "
                    "the price-anchor block says 'claude: Opus-class $15/$75' (Opus 4.1's price; today $4/$20); the header "
                    "says 'no luna row'; the MAINTENANCE header says 'never an automatic bump' while `opus: opus` moved to "
                    "Opus 5.5 by itself; the Claude top rung `fable` is reachable by the architecture class and by "
                    "escalation although the user decided 'Opus 5.5 reicht' (DEC-0114 (4)).",
        "expected": "DEC-0114 built: codex opus -> gpt-6-sol, sonnet -> gpt-6-luna; no price anywhere in the tier file, a "
                    "per-rung suitability line (source + read date) instead; Claude names stay pass-through and the file "
                    "says so truthfully; on Claude no path reaches Fable; restamp; the watcher definitions and the "
                    "kits' lead texts that describe the tiers agree with the file.",
        "repro": "grep -n 'gpt-5.6\\|\\$15/\\$75\\|luna row' team-kits/model_tiers.yaml",
        "severity": "medium",
        "acceptance_criteria": [
            {"id": "AC-1", "text": "a test NAMING this bug is red on 8677bd2's model_tiers.yaml and green after: no price "
                                   "figure in the file, a suitability line with read date per rung and provider, the "
                                   "codex rows are gpt-6-sol / gpt-6-luna / gpt-6-astra"},
            {"id": "AC-2", "text": "on the Claude side no class, pin or escalation step resolves to Fable, measured "
                                   "through the kernel's ladder answer for every kit, red before"},
        ],
        "source": "DEC-0114; radar/2026-09-25-claude-by-claude.md; radar/2026-09-25-codex-by-claude.md",
        "limits": "Nichts ist kaputt: die alten Codex-Modelle laufen noch, und die Claude-Namen zeigen schon auf das "
                  "neueste Modell. Falsch sind die Preisangaben und die oberste Claude-Stufe gegenüber deiner "
                  "Entscheidung vom 25.09.",
    },
    {
        "title": "Das Watcher-Werkzeug fuehrt noch die gestaffelten Tage Sa/So/Mo, obwohl DEC-0098 alle Watcher auf "
                 "Freitag ~20:00 gelegt hat",
        "related_pr": "PR-0012",
        "observed": "MEASURED 2026-09-25: tools/radar_routine.py SCHEDULE_AS_TOLD = friday/saturday/sunday/monday with "
                    "SCHEDULE_SOURCE 'DEC-0090 (4)'; `--describe` therefore tells the user to create the Codex "
                    "Automations on Sunday/Monday and the codex-watcher-by-claude run on Saturday, while DEC-0098 (1)/(2) "
                    "put all four on Friday ~20:00 and the Desktop task `watcher-duo` (created 2026-09-25) runs both "
                    "Claude-side watchers in ONE task. The stagger test "
                    "(test_the_routine_plan_covers_every_watcher_on_every_runner_and_staggers_them) pins the old shape.",
        "expected": "DEC-0098 (3): the schedule table says Friday ~20:00 for all four with DEC-0098 as its source; the "
                    "skip rule is expressed as 'one task per app runs its watchers in sequence' rather than 'different "
                    "weekdays'; the describe text for the Claude side names the one task watcher-duo.",
        "repro": "python tools/radar_routine.py --describe  -> schedule_as_told.day of codex-watcher-by-claude = saturday",
        "severity": "low",
        "acceptance_criteria": [
            {"id": "AC-1", "text": "a test NAMING this bug reads the declaration and is red on 8677bd2: every routine "
                                   "friday, source DEC-0098, and no two routines of the same runner as separate tasks "
                                   "at the same time"},
        ],
        "source": "DEC-0098; radar/routine.json (recorded_by, 2026-09-25)",
        "limits": "Nur die Beschreibung ist veraltet: die Desktop-Aufgabe läuft schon richtig freitags; wer die "
                  "Codex-Automationen nach dem Werkzeug anlegt, bekäme falsche Tage -- die richtigen Texte hat der "
                  "Nutzer im Chat bekommen.",
    },
]

env = dict(os.environ, PYTHONPATH="team-kits")
rc = 0
for body in BUGS:
    result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(body),
                            capture_output=True, text=True, encoding="utf-8")
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr[-1500:])
    rc = rc or result.returncode
sys.exit(rc)
