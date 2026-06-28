#!/usr/bin/env python3
"""
Shared helper: append a one-line record whenever a gate BLOCKS, so the (read-only) PM retro
has a data basis for "did this cycle run cleanly / were gates hit". Append-only JSONL under
project_memory/.audit/ — never project state, never blocks, best-effort (failures are swallowed).
"""
import json
import os
import time

try:
    from _root import find_repo_root
except Exception:
    def find_repo_root(start=None):
        return os.environ.get("CLAUDE_PROJECT_DIR") or start or os.getcwd()


def record(hook, reason):
    try:
        root = find_repo_root()
        d = os.path.join(root, "project_memory", ".audit")
        if not os.path.isdir(os.path.join(root, "project_memory")):
            return  # no project yet -> nothing to log
        os.makedirs(d, exist_ok=True)
        line = json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "hook": hook,
            "event": "block",
            "reason": (str(reason) or "")[:300],
        }, ensure_ascii=False)
        with open(os.path.join(d, "hook_events.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
