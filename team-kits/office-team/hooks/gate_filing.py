#!/usr/bin/env python3
"""
PostToolUse(Edit|Write) on filing_log.yaml — a filing claim is verified, not trusted.

Every `filed:` entry must point at a file that actually EXISTS under archive/ — "inbox processed"
with a phantom target is exactly the self-reported-success class this harness exists to kill.
Blocks with the missing entries listed. Uncertainty -> exit 0.
"""
import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit
import _compat


def check(data, path, root):
    if os.path.basename(path.replace("\\", "/")) != "filing_log.yaml":
        return
    if not os.path.isfile(path):
        return
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return
    try:
        doc = yaml.safe_load(open(path, encoding="utf-8", errors="ignore").read()) or {}
    except Exception:
        return  # guard_yaml_valid owns broken YAML

    problems = []
    for entry in (doc.get("filed") or []):
        if not isinstance(entry, dict):
            continue
        target = str(entry.get("target") or "").replace("\\", "/")
        if not target:
            problems.append("entry without target: %r" % entry.get("source"))
            continue
        if not target.startswith("archive/"):
            problems.append("%s -> %s (targets must live under archive/)" % (entry.get("source"), target))
            continue
        if not os.path.isfile(os.path.join(root, target)):
            problems.append("%s -> %s (file does NOT exist)" % (entry.get("source"), target))
    if problems:
        _audit.record("gate_filing", "; ".join(problems[:3]))
        message = (
            "[team-kit gate] filing_log.yaml claims filings that are not real:\n%s\n"
            "Move the file(s) under archive/ FIRST, then log — a log entry is a verified fact, "
            "not an intention.\n" % "\n".join("  - " + p for p in problems[:8])
        )
        _compat.stop(message, "PostToolUse")


def main():
    data = _compat.load()
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        sys.exit(0)
    root = find_repo_root(data.get("cwd"))
    for path in _compat.file_paths(data):
        check(data, path, root)
    sys.exit(0)


if __name__ == "__main__":
    main()
