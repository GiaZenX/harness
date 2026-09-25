#!/usr/bin/env python3
"""What the subagents of an order cost in context -- the before/after instrument of FR-0093.

WHAT IT READS, measured on this host on 2026-09-25 rather than assumed: Claude Code keeps one
transcript per subagent at `~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl`,
beside an `agent-<id>.meta.json` carrying `agentType`, `description` and `model`. `<project>` is
the working directory with every character that is not a letter or a digit turned into `-`
(`C:\\Offline Repos\\AgentAndSkills` -> `C--Offline-Repos-AgentAndSkills`). A transcript line of
`type: assistant` carries `message.id` and `message.usage`; ONE model call is written as several
lines when it returns several content blocks, each repeating the same id and the same usage -- so a
TURN here is a distinct `message.id`, never a line.

WHAT IT PRINTS, per agent: turns; the context each turn read (median and p90, nearest rank), which
is `input_tokens + cache_creation_input_tokens + cache_read_input_tokens` of that turn; the total
input read over all turns; and the POLLING turns -- a turn whose every tool call is a shell command
that waits (`sleep`, `Start-Sleep`, `timeout /t`), with the share of the input those turns read.
FR-0093's measurement found the driver to be context size times turns, not waiting; this prints
both so the next order can be compared with this one.

WHAT IT DOES NOT COUNT, named: a turn that only LOOKS at a log (`tail`, `Get-Content -Tail`) without
waiting is reading, not polling, and is not in the polling column; output tokens are not in the
input total; and an agent is attributed to an order only by `--item`, which asks whether the id
stands in the agent's FIRST prompt -- an agent whose order does not name the item is not counted.
`tools/test_measure_agent_tokens.py` holds the counts on a synthetic transcript.
"""
import argparse
import glob
import json
import os
import re
import statistics
import sys

# A shell command that WAITS: the command word of a sleep, in the spellings the two shells of this
# host run -- as a word of its own, so `sleepy.py` or a path segment is not one.
WAIT_RX = re.compile(r"(?:^|[\s;&|(])(?:sleep|Start-Sleep)(?=\s|$)|(?:^|[\s;&|(])timeout(?:\.exe)?\s+/t\b",
                     re.IGNORECASE)


def project_slug(path):
    """The directory name Claude Code keeps a project's transcripts under."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))


def default_project_dir(repo=None):
    root = repo or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", project_slug(root))


def nearest_rank(values, share):
    """The nearest-rank percentile -- a value that was really measured, never an interpolation."""
    ordered = sorted(values)
    if not ordered:
        return 0
    rank = max(1, -(-len(ordered) * share // 100))
    return ordered[int(rank) - 1]


def _text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(str(block.get("text") or "") for block in content if isinstance(block, dict))
    return ""


def read_transcript(path):
    """(first prompt text, {message id: (context read, [shell commands], [tool names])})."""
    first_prompt, turns = None, {}
    with open(path, encoding="utf-8", newline="") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
            if entry.get("type") == "user" and first_prompt is None:
                first_prompt = _text_of(message.get("content"))
            if entry.get("type") != "assistant" or not message.get("id"):
                continue
            usage = message.get("usage") or {}
            context = sum(int(usage.get(key) or 0) for key in (
                "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            read, commands, tools = turns.get(message["id"], (0, [], []))
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tools.append(str(block.get("name")))
                    tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
                    if "command" in tool_input:
                        commands.append(str(tool_input["command"]))
            turns[message["id"]] = (max(read, context), commands, tools)
    return first_prompt or "", turns


def is_polling(commands, tools):
    """A turn whose every tool call is a shell command, and every one of them waits."""
    return bool(tools) and len(commands) == len(tools) and all(WAIT_RX.search(c) for c in commands)


def measure(path):
    """One agent's numbers, off its transcript and the meta file beside it."""
    meta_path = path[:-len(".jsonl")] + ".meta.json"
    try:
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, ValueError):
        meta = {}
    prompt, turns = read_transcript(path)
    reads = [read for read, _commands, _tools in turns.values()]
    polling = [read for read, commands, tools in turns.values() if is_polling(commands, tools)]
    return {
        "agent": os.path.basename(path)[len("agent-"):-len(".jsonl")],
        "session": os.path.basename(os.path.dirname(os.path.dirname(path))),
        "type": meta.get("agentType"),
        "description": meta.get("description"),
        "model": meta.get("model"),
        "turns": len(turns),
        "context_median": int(statistics.median(reads)) if reads else 0,
        "context_p90": nearest_rank(reads, 90),
        "input_total": sum(reads),
        "polling_turns": len(polling),
        "polling_input": sum(polling),
        "first_prompt": prompt,
    }


def collect(project_dir, session=None, item=None):
    pattern = os.path.join(project_dir, session or "*", "subagents", "agent-*.jsonl")
    found = [measure(path) for path in sorted(glob.glob(pattern))]
    if item:
        found = [row for row in found if item in row["first_prompt"]]
    return found


def summary(rows):
    reads = [row["context_median"] for row in rows]
    total = sum(row["input_total"] for row in rows)
    polled = sum(row["polling_input"] for row in rows)
    return {
        "agents": len(rows),
        "turns": sum(row["turns"] for row in rows),
        "median_of_agent_medians": int(statistics.median(reads)) if reads else 0,
        "input_total": total,
        "polling_turns": sum(row["polling_turns"] for row in rows),
        "polling_share_of_input": round(polled / total, 4) if total else 0.0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--project-dir", default=None,
                        help="the transcripts directory (default: this repository's)")
    parser.add_argument("--session", default=None, help="one session id (default: all)")
    parser.add_argument("--item", default=None,
                        help="only agents whose first prompt names this id, e.g. TSK-0150")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args(argv)
    project_dir = args.project_dir or default_project_dir()
    if not os.path.isdir(project_dir):
        sys.stderr.write("no transcripts directory at %s\n" % project_dir)
        return 2
    rows = collect(project_dir, args.session, args.item)
    total = summary(rows)
    if args.json:
        print(json.dumps({"agents": [dict(row, first_prompt=None) for row in rows],
                          "summary": total}, indent=2))
        return 0
    print("%-19s %-20s %6s %10s %10s %13s %6s" % ("agent", "type", "turns", "ctx_med", "ctx_p90",
                                                  "input_total", "polls"))
    for row in rows:
        print("%-19s %-20s %6d %10d %10d %13d %6d" % (
            row["agent"][:19], str(row["type"])[:20], row["turns"], row["context_median"],
            row["context_p90"], row["input_total"], row["polling_turns"]))
    print("summary: " + json.dumps(total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
