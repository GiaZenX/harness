"""Capture the user's decisions of 2026-09-06 evening on the watcher duo: names (claude-watcher / codex-watcher),
rungs (the `opus` rung on both providers: Claude opus, Codex gpt-5.6-sol), every watcher run by BOTH providers
(four weekly runs), and who creates the four routines when. Body on stdin to `kernel.cli capture DEC`; `work`
is set afterwards on the TSK that carries it. Not idempotent -- run once."""
import json
import os
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KERNEL = [sys.executable, "-B", "-m", "kernel.cli", "--root", "project_memory", "capture", "DEC"]

BODY = {
    "title": "Watcher-Duo: radar-watcher heisst kuenftig claude-watcher (Gegenstueck codex-watcher), beide auf der "
             "opus-Sprosse (Claude opus, Codex gpt-5.6-sol), und JEDER Watcher laeuft ueber BEIDE Anbieter -- vier "
             "lokale Routinen (zwei Claude-Desktop-Aufgaben, zwei Codex-App-Automationen), angelegt beim naechsten "
             "lokalen Neustart",
    "context": "USER 2026-09-06 ~20:25, right after the DEC-0089 correction: 'ich wuerde gerne die Agenten umbenennen "
               "in claude watcher statt radar watcher -- macht mehr Sinn wenn der andere codex watcher heisst (oder "
               "openai watcher und anthropic watcher). Sie sollen das Modell opus5 tragen (und die Gegenpartei sol 5.6). "
               "Und beide Routinen sollen laufen sowohl von Claude als auch von Codex -- vielleicht finden sie andere "
               "Dinge. Wann richtest du die beiden ein?' MEASURED: both watcher definitions pin `model: sonnet` today "
               "(.claude/agents/radar-watcher.md:14, codex-watcher.md:14); the Codex overlays .codex/agents/"
               "radar-watcher.toml and codex-watcher.toml exist and carry NO model line; the three-rung ladder "
               "(G5-2, team-kits/model_tiers.yaml) maps the `opus` rung to claude `opus` and codex `gpt-5.6-sol` -- "
               "so 'opus 5 / sol 5.6' is exactly the opus rung on both providers, no new id; the report suffixes are "
               "already `-claude` and `-codex`, so the pair claude-watcher / codex-watcher matches what is on disk "
               "(anthropic/openai would rename fourteen reports' convention for nothing). Routines: the Claude Desktop "
               "scheduled task (DEC-0089) runs locally, schedule in the app; the Codex app (Windows since 2026-03-04, "
               "openai.com/index/introducing-the-codex-app) has Automations / scheduled tasks with the same shape -- "
               "local, app open, model and reasoning effort selectable, standard intervals or RRULE, results in a "
               "'Scheduled' inbox, no file on disk (learn.chatgpt.com/docs/automations, fetched 2026-09-06). Neither "
               "kind can be created from this remote session: this session has no scheduled-task tool (only the "
               "session-bound CronCreate that dies with it) and the Codex app is not reachable from here.",
    "decision": "(1) NAMES: `claude-watcher` (was radar-watcher) and `codex-watcher` -- the provider whose ecosystem "
                "the watcher scans, matching the report suffixes `-claude` / `-codex`; the files .claude/agents/"
                "claude-watcher.md and .codex/agents/claude-watcher.toml replace the radar-watcher pair, every citation "
                "in radar/README.md, radar/routine.json's shape, tools/radar_routine.py, the tests and the round texts "
                "follows; the report folder stays `radar/` and the tool keeps its name (radar = the duo's product, not "
                "one watcher). (2) RUNGS: both watchers pin the `opus` rung -- `model: opus` in the Claude definition, "
                "`model = \"gpt-5.6-sol\"` + `model_reasoning_effort = \"high\"` in the Codex overlays -- read from "
                "model_tiers.yaml through the generator, never typed twice; effort high (DEC-0076). (3) CROSS-PROVIDER: "
                "every watcher runs weekly under BOTH providers -- four runs: claude-watcher by Claude and by Codex, "
                "codex-watcher by Claude and by Codex; the report name carries the RUNNER too: radar/<date>-<watcher>-"
                "by-<runner>.md (e.g. 2026-09-11-claude-by-codex.md), so `--due` counts per watcher AND runner and two "
                "reports on one topic lie side by side; decided.md triage stays one list. (4) ROUTINES: four local "
                "routines -- two Claude Desktop scheduled tasks (claude-watcher Friday ~20:00 -- the existing task, "
                "re-pointed to the new file name; codex-watcher Saturday ~20:00) and two Codex app Automations "
                "(claude-watcher Sunday ~20:00, codex-watcher Monday ~20:00) -- staggered so no two run at once; the "
                "schedule lives in the apps, the repo records it in radar/routine.json AS TOLD, with the report cadence "
                "as the evidence (DEC-0089 (3)). (5) WHO / WHEN: the code side (rename, pins, runner suffix, texts, "
                "tests, red-first) is a work order under PR-0010 AFTER the generation-5 merge, one Opus builder; the "
                "four routines are created at the NEXT LOCAL SESSION on the user's machine -- the lead asks Claude "
                "Desktop to create/edit the two Claude tasks in that session (documented route: 'ask Claude in any "
                "Desktop session'), the user creates the two Codex Automations in the Codex app (the lead hands him "
                "the exact instructions text and schedule); nothing of this is possible from the remote session. "
                "(6) MEASURE FIRST at that restart: that the Codex app on this host shows Automations, and that a "
                "Codex run of the Claude definition (via the .codex overlay) writes the report in the shipped shape -- "
                "the first cross-provider report is PR-0010 AC-1's second half of evidence.",
    "consequences": "Two more weekly reports per topic, from a second model family -- what one misses the other may "
                    "find (the user's reason); cost: four local runs a week on the opus rung, the machine on at the "
                    "four times. Rejected: anthropic-watcher / openai-watcher (breaks the suffix convention on disk), "
                    "keeping sonnet (the user wants the stronger rung for a read-only scan whose value is judgment), "
                    "a cloud routine (DEC-0089), creating routines remotely (no tool).",
    "source": "user message 2026-09-06 evening; .claude/agents/radar-watcher.md + codex-watcher.md; .codex/agents/*.toml; "
              "team-kits/model_tiers.yaml (G5-2 worktree); DEC-0089; DEC-0076; PR-0010; learn.chatgpt.com/docs/automations; "
              "openai.com/index/introducing-the-codex-app; code.claude.com/docs/en/desktop-scheduled-tasks",
}

env = dict(os.environ, PYTHONPATH="team-kits")
result = subprocess.run(KERNEL, cwd=ROOT, env=env, input=json.dumps(BODY),
                        capture_output=True, text=True, encoding="utf-8")
sys.stdout.write(result.stdout)
sys.stderr.write(result.stderr)
sys.exit(result.returncode)
