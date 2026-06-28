#!/usr/bin/env python3
"""
retro.py — a READ-ONLY diagnostic retro for the PM.

Aggregates the facts of recent work (git history, QA failures, gate blocks from the hook event log,
task churn) and appends a dated entry to project_memory/retro.yaml. It writes ONLY retro.yaml (its own
append-only diagnostic layer) — never project state, so it does not become a second writer (§6). Run it
manually, from CI, or from a scheduled agent; an Opus agent may then read retro.yaml and turn the facts
into concrete advice for the PM (and the PM's agent-memory).

Usage: python scripts/retro.py [--since "2 days ago"]
"""
import collections
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PM = os.path.join(ROOT, "project_memory")


def git(*args):
    try:
        r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=20)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def read(path):
    try:
        return open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""


def main():
    since = "7 days ago"
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]
    if not os.path.isdir(PM):
        print("[retro] no project_memory/ — nothing to review.")
        return

    commits = [ln for ln in git("log", "--since", since, "--oneline").splitlines() if ln.strip()]

    # QA failures across report files
    qa_fail = 0
    for fn in ("test_reports.yaml", "review_reports.yaml", "acceptance_reports.yaml",
               "validation_reports.yaml"):
        t = read(os.path.join(PM, fn))
        qa_fail += len(re.findall(r"(?mi)^\s*(result|verdict):\s*fail", t))
    qa_failures_field = sum(int(x) for x in re.findall(r"(?mi)qa_failures:\s*(\d+)",
                                                       read(os.path.join(PM, "tasks.yaml"))))

    # gate blocks from the hook event log
    blocks = collections.Counter()
    log = os.path.join(PM, ".audit", "hook_events.jsonl")
    if os.path.isfile(log):
        for line in read(log).splitlines():
            try:
                blocks[json.loads(line).get("hook", "?")] += 1
            except Exception:
                pass

    # task churn
    tasks = read(os.path.join(PM, "tasks.yaml"))
    rejected = len(re.findall(r"(?mi)status:\s*REJECTED", tasks))

    findings = []
    if blocks:
        findings.append("gates blocked work: " + ", ".join("%s x%d" % (k, v) for k, v in blocks.most_common()))
    if qa_fail:
        findings.append("%d QA FAIL verdict(s) recorded" % qa_fail)
    if qa_failures_field:
        findings.append("%d cumulative task qa_failures (model/escalation signal)" % qa_failures_field)
    if rejected:
        findings.append("%d task(s) ended REJECTED (re-scoping churn)" % rejected)
    if blocks.get("guard_pm_scope"):
        findings.append("the PM tried to write code %d time(s) — should delegate" % blocks["guard_pm_scope"])
    if not findings:
        findings.append("clean: no gate blocks, QA failures or rejected tasks in the window")

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    entry = (
        "  - date: %s\n"
        "    window: \"%s\"\n"
        "    commits: %d\n"
        "    qa_fail_verdicts: %d\n"
        "    gate_blocks: %s\n"
        "    findings:\n%s\n"
        % (stamp, since, len(commits), qa_fail,
           (json.dumps(dict(blocks)) if blocks else "{}"),
           "\n".join("      - %s" % f for f in findings))
    )
    out = os.path.join(PM, "retro.yaml")
    if not os.path.isfile(out):
        open(out, "w", encoding="utf-8").write(
            "# retro.yaml — READ-ONLY diagnostic layer (written by scripts/retro.py, append-only).\n"
            "# NOT project state. The PM reads it for feedback; it is never a source of requirements.\n"
            "retros:\n")
    with open(out, "a", encoding="utf-8") as fh:
        fh.write(entry)

    print("[retro] %d commits, %d QA fails, blocks=%s" % (len(commits), qa_fail, dict(blocks)))
    for f in findings:
        print("  - " + f)
    print("[retro] appended to project_memory/retro.yaml")


if __name__ == "__main__":
    main()
