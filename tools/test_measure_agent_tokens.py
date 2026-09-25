#!/usr/bin/env python3
"""`tools/measure_agent_tokens.py` on a synthetic transcript in the layout Claude Code writes
(FR-0093's before/after instrument).

Each count is held where it can go wrong: one model call written as TWO lines (two content blocks,
the same `message.id` and usage) is one turn and is read once; a turn that waits is a polling turn
in both shells' spellings, and one that only looks at a log is not; a turn that waits AND does
something else is not polling; `--item` keeps only the agents whose FIRST prompt names the id (a
later user line naming another item does not count). The
script is also run as a PROCESS against the synthetic project directory, so what is measured is what
the lead would see.
"""
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from conftest import load_kit_module  # noqa: E402 -- the suite's one loader for shipped scripts

SCRIPT = os.path.join(ROOT, "tools", "measure_agent_tokens.py")
measure = load_kit_module("measure_agent_tokens_under_test", SCRIPT)


def _assistant(message_id, context, *blocks):
    third = context // 3
    return {"type": "assistant", "message": {
        "id": message_id, "role": "assistant", "content": list(blocks),
        "usage": {"input_tokens": context - 2 * third, "cache_creation_input_tokens": third,
                  "cache_read_input_tokens": third, "output_tokens": 7}}}


def _shell(command, name="Bash"):
    return {"type": "tool_use", "name": name, "input": {"command": command}}


def _write_agent(project, session, agent, prompt, lines):
    where = os.path.join(project, session, "subagents")
    os.makedirs(where, exist_ok=True)
    with io.open(os.path.join(where, "agent-%s.jsonl" % agent), "w", encoding="utf-8",
                 newline="\n") as handle:
        handle.write(json.dumps({"type": "user", "message": {"role": "user", "content": prompt}}) + "\n")
        for line in lines:
            handle.write(json.dumps(line) + "\n")
        handle.write("not json at all\n")
    with io.open(os.path.join(where, "agent-%s.meta.json" % agent), "w", encoding="utf-8",
                 newline="\n") as handle:
        json.dump({"agentType": "harness-implementer", "description": "d", "model": "opus"}, handle)


def _project(tmp_path):
    project = str(tmp_path / "C--repo")
    _write_agent(project, "s1", "a1", "Your order is TSK-0150 -- build it.", [
        # one call, two content blocks: ONE turn of 100
        _assistant("m1", 100, {"type": "text", "text": "reading"}),
        _assistant("m1", 100, _shell("cat big.txt")),
        _assistant("m2", 300, _shell("sleep 60")),                                  # polling
        _assistant("m3", 200, _shell("Start-Sleep -Seconds 30", "PowerShell")),   # polling
        _assistant("m4", 400, _shell("tail -5 run.log")),                          # a look, no wait
        # a LATER user line naming another item: `--item` reads the FIRST prompt only
        {"type": "user", "message": {"role": "user", "content": [
            {"type": "text", "text": "a note about TSK-0151"},
            {"type": "tool_result", "content": "ok"}]}},
        _assistant("m5", 500, _shell("sleep 5"), _shell("python -m pytest")),      # waits AND works
        _assistant("m6", 600, _shell("python sleepy.py")),                         # not a sleep word
    ])
    _write_agent(project, "s1", "a2", "An order for TSK-0151.", [_assistant("x1", 50)])
    return project


def test_the_counts_on_a_synthetic_transcript(tmp_path):
    """Turns by message id, context per turn, the nearest-rank p90, and the polling definition."""
    rows = measure.collect(_project(tmp_path))
    row = {one["agent"]: one for one in rows}["a1"]
    assert row["turns"] == 6, row
    assert row["input_total"] == 100 + 300 + 200 + 400 + 500 + 600, row
    assert row["context_median"] == 350 and row["context_p90"] == 600, row
    assert row["polling_turns"] == 2 and row["polling_input"] == 500, row
    assert row["type"] == "harness-implementer" and row["session"] == "s1", row
    assert measure.nearest_rank([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90) == 9
    assert measure.nearest_rank([], 90) == 0
    assert measure.project_slug(r"C:\Offline Repos\AgentAndSkills").endswith(
        "C--Offline-Repos-AgentAndSkills")


def test_the_item_filter_and_the_process(tmp_path):
    """`--item` keeps the agents whose first prompt names the id; the process prints the summary."""
    project = _project(tmp_path)
    assert [row["agent"] for row in measure.collect(project, item="TSK-0150")] == ["a1"]
    assert [row["agent"] for row in measure.collect(project, item="TSK-0151")] == ["a2"]
    run = subprocess.run([sys.executable, "-B", SCRIPT, "--project-dir", project, "--item",
                          "TSK-0150", "--json"], capture_output=True, text=True, encoding="utf-8",
                         timeout=60)
    assert run.returncode == 0, run.stderr
    shown = json.loads(run.stdout)
    assert shown["summary"]["agents"] == 1 and shown["summary"]["turns"] == 6, shown["summary"]
    assert shown["summary"]["polling_share_of_input"] == round(500 / 2100, 4), shown["summary"]
    missing = subprocess.run([sys.executable, "-B", SCRIPT, "--project-dir",
                              str(tmp_path / "nowhere")], capture_output=True, text=True,
                             encoding="utf-8", timeout=60)
    assert missing.returncode == 2 and "no transcripts directory" in missing.stderr
