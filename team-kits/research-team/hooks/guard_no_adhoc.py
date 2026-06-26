#!/usr/bin/env python3
"""
PreToolUse(Write) guard — enforces the single-source-of-truth rule.

Blocks the creation of ad-hoc status/summary/report/result files that the agents
kept inventing instead of writing the predefined project_memory/*.yaml. Reads the
Claude Code hook JSON from stdin; exit code 2 + a stderr message blocks the tool call
and tells the model why. Any uncertainty -> exit 0 (never block legitimate work).
"""
import sys
import os
import re
import json
import fnmatch

# Filename patterns that are always ad-hoc dumps (seen in real runs).
DENY_NAME = [
    "*_summary.md", "*_summary.txt", "*_result.yaml", "*_result.yml", "*_result.json",
    "*_report.md", "*_report.txt", "backend_result_*", "frontend_result_*",
    "delegation_*", "implementation_summary.*", "*_release_summary.md",
    "*_discovery_report.md",
]

ALLOWED_ROOT_DOCS = {
    "readme.md", "claude.md", "contributing.md", "changelog.md", "license", "license.md",
    "code_of_conduct.md", "security.md",
}


def block(rel, why):
    sys.stderr.write(
        "[team-kit guard] Blocked creating '%s': %s.\n"
        "Single source of truth = project_memory/*.yaml (+ src/ + tests/). "
        "Reviews -> review_reports.yaml, tests -> test_reports.yaml, "
        "acceptance -> acceptance_reports.yaml, architecture -> architecture.yaml/decisions.yaml. "
        "Put the content into the correct YAML instead of a new file.\n" % (rel, why)
    )
    sys.exit(2)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Write":
        sys.exit(0)
    inp = data.get("tool_input") or {}
    path = inp.get("file_path") or inp.get("path") or ""
    if not path:
        sys.exit(0)
    cwd = data.get("cwd") or os.getcwd()
    try:
        rel = os.path.relpath(path, cwd)
    except Exception:
        rel = path
    rel = rel.replace("\\", "/").lstrip("./")
    name = os.path.basename(rel).lower()
    is_root = "/" not in rel

    # 1) explicit ad-hoc dump patterns, anywhere
    for pat in DENY_NAME:
        if fnmatch.fnmatch(name, pat):
            block(rel, "matches a forbidden ad-hoc report/summary pattern")

    # 2) requirement/task status written as a markdown doc (PRD-002_*.md etc.), anywhere
    if name.endswith(".md") and re.match(r"^(prd|rq|exp|sr|tsk|cr|pa|adr|mdr|hyp)-\d", name):
        block(rel, "requirement/task status belongs in project_memory/*.yaml, not a markdown file")

    # 3) loose markdown at the repo root (except the few conventional ones)
    if is_root and name.endswith(".md") and name not in ALLOWED_ROOT_DOCS:
        block(rel, "no loose docs at the repo root; put status/notes into project_memory/*.yaml or docs/")

    sys.exit(0)


if __name__ == "__main__":
    main()
