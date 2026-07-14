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


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit
import _compat


def block(rel, why):
    _audit.record("guard_no_adhoc", rel)
    sys.stderr.write(
        "[team-kit guard] Blocked creating '%s': %s.\n"
        "Single source of truth = project_memory/*.yaml (+ src/ + tests/). "
        "Reviews -> review_reports.yaml, tests -> test_reports.yaml, "
        "acceptance -> acceptance_reports.yaml, architecture -> architecture.yaml/decisions.yaml. "
        "Put the content into the correct YAML instead of a new file.\n" % (rel, why)
    )
    sys.exit(2)


def check(path, cwd):
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


def main():
    data = _compat.load()
    allowed_roles = {role for role in os.environ.get("TEAM_KIT_AGENT_TYPES", "").split(",")
                     if role}
    if allowed_roles and str(data.get("agent_type") or "") not in allowed_roles:
        sys.exit(0)
    # Claude exposes a dedicated Write event. Codex batches Add/Update/Delete/Move operations into
    # one apply_patch call, so inspect only paths actually created by Add File or Move to.
    paths = (_compat.created_file_paths(data) if data.get("_file_operations")
             else _compat.file_paths(data) if data.get("tool_name") == "Write" else [])
    if not paths:
        sys.exit(0)
    cwd = find_repo_root(data.get("cwd"))
    for path in paths:
        check(path, cwd)
    sys.exit(0)


if __name__ == "__main__":
    main()
