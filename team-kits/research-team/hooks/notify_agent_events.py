#!/usr/bin/env python3
"""
Notification + SubagentStop hook — deterministic audit log for agent lifecycle events.

The delegation rule (spawn `run_in_background: false`, or deliberately parallelize and await ALL
completions) was prompt-level only; a real run spawned 37/37 specialists background-by-default with
zero accounting. This hook appends lifecycle events to project_memory/.audit/hook_events.jsonl so
spawn accounting is auditable (retro.py) instead of trusted. Two routes, because a real session
showed the Notification route alone delivering NOTHING (0 of 15 completions — the platform injected
task results as messages instead): (a) Notification with `notification_type: agent_completed |
agent_needs_input` (kept for environments that fire it), (b) SubagentStop, which fires whenever a
subagent finishes. Spawn-side accounting lives in guard_agent_spawn (event: spawn). Never blocks,
never prints — exit 0 always.
"""
import json
import os
import sys
import time


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from _root import find_repo_root
except Exception:
    def find_repo_root(start=None):
        return os.environ.get("CLAUDE_PROJECT_DIR") or start or os.getcwd()


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    hev = str(data.get("hook_event_name") or "")
    if hev in ("SubagentStart", "SubagentStop"):
        event = "subagent_start" if hev == "SubagentStart" else "subagent_stop"
        reason = str(data.get("agent_type") or data.get("agent_name")
                     or data.get("agent_id") or "")[:300]
    else:
        event = str(data.get("notification_type") or "")
        if event not in ("agent_completed", "agent_needs_input"):
            sys.exit(0)
        reason = str(data.get("message") or "")[:300]
    try:
        root = find_repo_root(data.get("cwd"))
        if not os.path.isdir(os.path.join(root, "project_memory")):
            sys.exit(0)  # no project yet -> nothing to log
        d = os.path.join(root, "project_memory", ".audit")
        os.makedirs(d, exist_ok=True)
        line = json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "hook": "notify_agent_events",
            "event": event,
            "reason": reason,
        }, ensure_ascii=False)
        with open(os.path.join(d, "hook_events.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # best-effort logging must never break a session
    sys.exit(0)


if __name__ == "__main__":
    main()
